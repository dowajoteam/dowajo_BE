import logging
import httpx
import asyncio
import time
import re
from django.http import JsonResponse
from secrets_manager import get_openai_secret_key
from secrets_manager import get_naver_client_id
from secrets_manager import get_naver_client_secret
import openai
from rest_framework.views import APIView
from rest_framework import status

NAVER_CLIENT_ID = get_naver_client_id()
NAVER_CLIENT_SECRET = get_naver_client_secret()
RATE_LIMIT = 10  # Naver API rate limit: 10 requests per second
MAX_RETRIES = 5  # Maximum number of retries for rate limiting

class RestaurantListView(APIView):
    pending_requests = {}

    def get(self, request, *args, **kwargs):
        result = asyncio.run(self.async_get_data(request))
        return JsonResponse(result, status=status.HTTP_200_OK, safe=False)

    async def async_get_data(self, request):
        query = request.query_params.get('keyword', '')
        if query in self.pending_requests:
            return await self.pending_requests[query]

        future = asyncio.Future()
        self.pending_requests[query] = future

        try:
            result = await self._process_request(query)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        finally:
            del self.pending_requests[query]

        return await future

    async def _process_request(self, query):
        start_time = time.time()
        logging.info(f"Query: {query}")

        blog_items = await self.fetch_blog_data(query)
        if not blog_items:
            return {'error': 'No blog items found'}

        restaurant_names_list = await self.extract_restaurant_names(blog_items)
        formatted_names_list = self.format_names(restaurant_names_list)
        restaurant_address_dict = await self.fetch_restaurant_addresses(formatted_names_list)
        restaurant_summary_list = await self.fetch_restaurant_summaries(restaurant_address_dict, query)

        total_time = time.time() - start_time
        logging.info(f"Total time for async_get_data: {total_time:.2f} seconds")
        return restaurant_summary_list

    async def fetch_blog_data(self, query):
        start_time = time.time()
        blog_search_url = "https://openapi.naver.com/v1/search/blog.json"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }
        params = {"query": "내돈내산 맛집" + query, "display": 15, "start": 1}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(blog_search_url, headers=headers, params=params)
                response.raise_for_status()
                logging.info(f"Fetch Blog Data Response Status: {response.status_code}")
                json_data = response.json()
                elapsed_time = time.time() - start_time
                logging.info(f"Time for fetch_blog_data: {elapsed_time:.2f} seconds")
                return json_data.get('items', [])
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"An error occurred: {e}")

        return []

    async def extract_restaurant_names(self, items):
        start_time = time.time()
        secret_key = get_openai_secret_key()
        openai.api_key = secret_key
        ques = str(items) + "에서 음식점명 10개를 중복없이 음식점명과 동네만 문자열로 들어있는 리스트로 반환해줘 부가적인 말은 하지마"

        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": ques},
                ]
            )
            restaurant_names_text = response.choices[0].message['content']
            restaurant_names_list = eval(restaurant_names_text)
            elapsed_time = time.time() - start_time
            logging.info(f"Time for extract_restaurant_names: {elapsed_time:.2f} seconds")
            return restaurant_names_list
        except Exception as e:
            logging.error(f"An error occurred while extracting restaurant names: {e}")
            return []

    def format_names(self, names_list):
        start_time = time.time()
        formatted_names_list = [re.sub(r'\s*\([^)]*\)', '', name).strip() for name in names_list]
        formatted_names_list = [name.replace(" - ", " ").strip() for name in formatted_names_list]
        elapsed_time = time.time() - start_time
        logging.info(f"Time for format_names: {elapsed_time:.2f} seconds")
        return formatted_names_list

    async def fetch_restaurant_addresses(self, names_list):
        start_time = time.time()
        local_search_url = "https://openapi.naver.com/v1/search/local.json"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }
        restaurant_address_dict = {}

        sem = asyncio.Semaphore(RATE_LIMIT)  # 동시 요청 수를 제한하기 위한 세마포어

        async def fetch_address(name, retries=0):
            params = {"query": name, "display": 1}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(local_search_url, headers=headers, params=params)
                    response.raise_for_status()
                    local_json_data = response.json()
                    local_items = local_json_data.get('items', [])
                    if local_items:
                        restaurant_name = local_items[0]['title'].replace('<b>', '').replace('</b>', '')
                        address = local_items[0]['address']
                        restaurant_address_dict[restaurant_name] = address
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and retries < MAX_RETRIES:
                    retry_delay = 2 ** retries
                    logging.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    await fetch_address(name, retries + 1)
                else:
                    logging.error(f"HTTP error occurred: {e}")
            except Exception as e:
                logging.error(f"An error occurred while fetching address: {e}")

        async def rate_limited_fetch(name):
            async with sem:
                await fetch_address(name)

        tasks = [rate_limited_fetch(name) for name in names_list]
        await self.rate_limiter(tasks, RATE_LIMIT)

        elapsed_time = time.time() - start_time
        logging.info(f"Time for fetch_restaurant_addresses: {elapsed_time:.2f} seconds")
        return restaurant_address_dict

    async def fetch_restaurant_summaries(self, address_dict, query):
        start_time = time.time()
        blog_search_url = "https://openapi.naver.com/v1/search/blog.json"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }
        secret_key = get_openai_secret_key()
        openai.api_key = secret_key
        restaurant_summary_list = []

        sem = asyncio.Semaphore(RATE_LIMIT)  # 동시 요청 수를 제한하기 위한 세마포어

        async def fetch_summary(name, retries=0):
            summary_query = f"{name} {query}"
            params = {"query": summary_query, "display": 5, "start": 1}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(blog_search_url, headers=headers, params=params)
                    response.raise_for_status()
                    json_data = response.json()
                    items = json_data.get('items', [])

                    # 블로그 URL을 수집합니다
                    blog_urls = [item['link'] for item in items[:2]]  # 상위 2개의 블로그 URL

                    descriptions = [item['description'] for item in items]

                    ques = str(descriptions) + "여기서 이 음식점에 대한 공백 포함 약 100자 요약 및 키워드 5개를 각각 20글자 이내로 뽑아줘 형식은 description: 요약 내용 keyword1: 내용 이런식이고 특수문자는 포함하지마"

                    openai_response = await openai.ChatCompletion.acreate(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": ques},
                        ]
                    )
                    blog_zip = openai_response.choices[0].message['content']

                    # Extracting description and keywords from the OpenAI response
                    lines = blog_zip.split('\n')
                    description = None
                    keywords = {}
                    for line in lines:
                        if line.startswith("description:"):
                            description = line[len("description:"):].strip()
                        elif line.startswith("keyword"):
                            key_number = line.split(':')[0].replace('keyword', '').strip()
                            key_value = line.split(':')[1].strip()
                            keywords[f"keyword{key_number}"] = key_value

                    # Constructing the summary dictionary
                    if description:
                        restaurant_summary_list.append({
                            "restaurant_name": name,
                            "restaurant_address": address_dict.get(name, "주소 없음"),
                            "description": description,
                            **keywords,
                            "blog_url1": blog_urls[0] if len(blog_urls) > 0 else "URL 없음",
                            "blog_url2": blog_urls[1] if len(blog_urls) > 1 else "URL 없음"
                        })

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and retries < MAX_RETRIES:
                    retry_delay = 2 ** retries
                    logging.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    await fetch_summary(name, retries + 1)
                else:
                    logging.error(f"HTTP error occurred: {e}")
            except Exception as e:
                logging.error(f"An error occurred while fetching summary: {e}")

        async def rate_limited_fetch(name):
            async with sem:
                await fetch_summary(name)

        tasks = [rate_limited_fetch(name) for name in address_dict.keys()]
        await self.rate_limiter(tasks, RATE_LIMIT)

        elapsed_time = time.time() - start_time
        logging.info(f"Time for fetch_restaurant_summaries: {elapsed_time:.2f} seconds")
        return restaurant_summary_list

    async def rate_limiter(self, tasks, rate_limit):
        semaphore = asyncio.Semaphore(rate_limit)
        async def limited_task(task):
            async with semaphore:
                await task
        await asyncio.gather(*(limited_task(task) for task in tasks))
