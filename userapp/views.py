from django.shortcuts import render

# myapp/views.py

import requests #http 요청을 보내는데 사용
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from .models import User
from .serializers import UserSerializer

class KakaoLoginView(APIView):
    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({"error": "Access token is required"}, status=status.HTTP_400_BAD_REQUEST)

        kakao_user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        kakao_response = requests.get(kakao_user_info_url, headers=headers)

        if kakao_response.status_code != 200:
            return Response({"error": "Failed to get user info from Kakao"}, status=status.HTTP_400_BAD_REQUEST)

        kakao_user_info = kakao_response.json()

        kakao_id = kakao_user_info['id']
        nickname = kakao_user_info['properties']['nickname']
        profile_image_url = kakao_user_info['properties'].get('profile_image', '')


        # 사용자 생성 혹은 업데이트
        user, created = User.objects.get_or_create(
            kakao_id=kakao_id,
            defaults={
                "nickname": nickname,
                "profile_image_url": profile_image_url

            }
        )

        if not created:
            # 기존 유저의 정보 업데이트
            user.nickname = nickname
            user.profile_image_url = profile_image_url
            user.save()

        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
