from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "refresh": data["refresh"],
                "access": data["access"],
                "user": {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                },
            },
        }