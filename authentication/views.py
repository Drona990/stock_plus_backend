import uuid

from django.db.models import Q
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from core.permissions import IsAccountActive, IsAdminOrSuperuser, IsSuperuser
from inventory.models import Location
from .models import CustomUser, OTP, RecoveryContact
from .serializers import *
from .utils.otp import generate_otp
from .utils.email import send_otp_email
from .utils.response import success_response, error_response
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum
from django.utils import timezone
from django.db import transaction

# ===== ROLE-BASED PERMISSION CLASSES =====

class HealthCheckView(APIView):
    authentication_classes = [AllowAny] 
    permission_classes = [AllowAny] 

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "message": "Restaurant backend is running 🚀"
            },
            status=status.HTTP_200_OK
        )

# ===== ROLE MANAGEMENT VIEWS =====

class CreateFirstSuperuserView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if CustomUser.objects.filter(role='superuser').exists():
            return error_response(
                "Superuser already exists. Cannot create another.",
                403
            )

        serializer = CreateSuperuserSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, 400)

        email = serializer.validated_data['email']
        
        # Generate username from email
        username = email.split('@')[0]
        counter = 1
        original_username = username
        while CustomUser.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1

        user = CustomUser.objects.create_superuser(
            username=username,
            email=email,
            password=serializer.validated_data['password'],
            role='superuser',
            is_verified=True,
            is_password_set=True,
        )

        return success_response(
            "Superuser created successfully",
            data={
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "message": "You can now login and create admin accounts"
            },
            status_code=201
        )



# --- 1. CREATE STAFF VIEW (With 5 User Limit for Admins) ---
class CreateStaffView(APIView):
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]

    def post(self, request):
        print(f"\n--- [LOG: CREATE STAFF STARTED] ---")
        print(f"Payload: {request.data}")

        serializer = CreateStaffSerializer(data=request.data)
        if not serializer.is_valid():
            print(f"❌ Serializer Errors: {serializer.errors}")
            return Response(serializer.errors, status=400)

        # ✅ LOGIC: Admin/Manager can create ONLY 5 staff members
        if request.user.role == 'admin':
            staff_count = CustomUser.objects.filter(created_by=request.user).count()
            if staff_count >= 5:
                return error_response("Limit reached: You can only create a maximum of 5 staff members.", 400)

        v_data = serializer.validated_data
        try:
            with transaction.atomic():
                # Unique Username Logic
                uname = v_data['email'].split('@')[0]
                while CustomUser.objects.filter(username=uname).exists():
                    uname = f"{uname}{uuid.uuid4().hex[:4]}"

                # ✅ MANUAL OBJECT CREATION (Ensures all fields save)
                user = CustomUser(
                    username=uname,
                    email=v_data['email'],
                    first_name=request.data.get('first_name', ''),
                    last_name=request.data.get('last_name', ''),
                    name=request.data.get('name', ''),
                    phone_number=request.data.get('phone_number', ''),
                    dob=request.data.get('dob'),
                    gender=request.data.get('gender', 'M'),
                    role='staff',
                    created_by=request.user,
                    is_verified=True,
                    is_active=True
                )

                # Location handling
                loc_id = request.data.get('location')
                if loc_id:
                    user.location = Location.objects.filter(id=loc_id).first()

                user.set_password(v_data['password'])
                user.save() 
                
                if user.email:
                    RecoveryContact.objects.get_or_create(
                        user=user, contact_type="email", 
                        contact_value=user.email, defaults={'is_verified': True}
                    )

            print(f"✅ DB SUCCESS: Staff {user.username} saved with Location: {user.location}")
            return Response({"success": True, "id": str(user.id)}, status=201)

        except Exception as e:
            print(f"🔥 ERROR: {str(e)}")
            return Response({"error": str(e)}, status=500)



# --- CREATE ADMIN VIEW (Fixed logic for data save) ---
class CreateAdminView(APIView):
    permission_classes = [IsSuperuser,IsAccountActive]

    def post(self, request):
        print(f"\n--- [DEBUG: CREATE ADMIN REQUEST] ---")
        print(f"RAW DATA: {request.data}")

        serializer = CreateAdminSerializer(data=request.data)
        if not serializer.is_valid():
            print(f"❌ SERIALIZER ERRORS: {serializer.errors}")
            return error_response(serializer.errors, 400)

        v_data = serializer.validated_data
        try:
            with transaction.atomic():
                # Unique Username Generation
                uname = v_data['email'].split('@')[0]
                while CustomUser.objects.filter(username=uname).exists():
                    uname = f"{uname}{uuid.uuid4().hex[:4]}"

                # ✅ FORCED SAVE: Direct initialization with all fields
                user = CustomUser(
                    username=uname,
                    email=v_data['email'],
                    first_name=v_data.get('first_name', ''),
                    last_name=v_data.get('last_name', ''),
                    name=v_data.get('name', f"{v_data.get('first_name', '')} {v_data.get('last_name', '')}".strip()),
                    phone_number=v_data.get('phone_number', ''),
                    dob=v_data.get('dob'),
                    gender=v_data.get('gender', 'M'),
                    role='admin', # Fixed role as admin
                    created_by=request.user,
                    is_verified=True,
                    is_password_set=True,
                    is_active=True
                )

                # Location Mapping (Integer ID to Object)
                loc_id = v_data.get('location')
                if loc_id:
                    user.location = Location.objects.filter(id=loc_id).first()

                user.set_password(v_data['password'])
                user.save() # Commit to DB

                if user.email:
                    RecoveryContact.objects.get_or_create(
                        user=user, contact_type="email", 
                        contact_value=user.email, defaults={'is_verified': True}
                    )

                print(f"✅ DB SUCCESS: Admin {user.username} saved with DOB: {user.dob}")

            return success_response("Admin created successfully", data={"user_id": str(user.id)}, status_code=201)

        except Exception as e:
            print(f"🔥 DB ERROR: {str(e)}")
            return error_response(str(e), 500)

# --- 2. UPDATE PROFILE VIEW (Admin/Superuser Permission Only) ---
class AdminUpdateUserView(APIView):
    """Admin updates another user's profile. Staff is blocked."""
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]

    def put(self, request, user_id):
        # 1. Access Check: Staff block
        if request.user.role == 'staff':
            return error_response("Access Denied: Staff cannot update user profiles.", 403)

        # 2. Get User (Handles UUID correctly)
        user_to_edit = get_object_or_404(CustomUser, id=user_id)

        # 3. Ownership Check: Admin only edits their own created staff
        if request.user.role != 'superuser' and user_to_edit.created_by != request.user:
            return error_response("Permission Denied: You didn't create this user.", 403)

        # 4. Update fields
        if 'name' in request.data: user_to_edit.name = request.data['name']
        if 'phone_number' in request.data: user_to_edit.phone_number = request.data['phone_number']
        if 'dob' in request.data: user_to_edit.dob = request.data['dob']
        if 'gender' in request.data: user_to_edit.gender = request.data['gender']
        
        if 'location' in request.data:
            loc_id = request.data['location']
            user_to_edit.location = get_object_or_404(Location, id=loc_id)

        # ✅ FIXED: Password update logic
        if 'password' in request.data and request.data['password']:
            user_to_edit.set_password(request.data['password'])
            user_to_edit.is_password_set = True

        user_to_edit.save()
        return success_response("User profile updated successfully")


# --- 4. SELF PROFILE UPDATE (Blocked for Staff if needed) ---
class UpdateProfileView(APIView):
    """User updates their own profile"""
    permission_classes = [IsAuthenticated,IsAccountActive]

    def patch(self, request):
        # ✅ LOGIC: If you want to block staff even from updating their OWN profile
        if request.user.role == 'staff':
            return error_response("Staff accounts are not permitted to modify profile data.", 403)

        serializer = UpdateProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(serializer.errors, 400)

        user = request.user
        if 'name' in serializer.validated_data: user.name = serializer.validated_data['name']
        if 'dob' in serializer.validated_data: user.dob = serializer.validated_data['dob']
        if 'gender' in serializer.validated_data: user.gender = serializer.validated_data['gender']
        
        user.save()
        return success_response("Profile updated successfully", data={"user_id": str(user.id), "name": user.name})



class ListStaffView(APIView):
    """Admin/Superuser views members created by them"""
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]

    def get(self, request):
        if request.user.role == 'superuser':
            staff = CustomUser.objects.exclude(role='superuser')
        else:
            staff = CustomUser.objects.filter(created_by=request.user)

        data = []
        for user in staff:
            # ✅ Fix: Convert Location object to a serializable dictionary
            location_data = None
            if user.location:
                location_data = {
                    "id": user.location.id,
                    "name": user.location.name
                }

            data.append({
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "name": user.name,
                "dob": user.dob,
                "gender": user.gender,
                "location": location_data, # 👈 Now it's a dict, not an object
                "is_active": user.is_active,
                "created_at": user.date_joined,
                "role": user.role,
            })

        return success_response("Staff list retrieved", data=data)
    

class ListAdminsView(APIView):
    """Superuser views all admins"""
    permission_classes = [IsSuperuser]

    def get(self, request):
        admins = CustomUser.objects.filter(role='admin')

        data = []
        for user in admins:
            location_data = None
            if user.location:
                location_data = {
                    "id": user.location.id,
                    "name": user.location.name
                }

            data.append({
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "name": user.name,
                "is_active": user.is_active,
                "location": location_data, # 👈 Fix here too
                "staff_count": user.created_users.filter(role='staff').count(),
                "created_at": user.date_joined
            })

        return success_response("Admins list retrieved", data=data)



class UserStatusToggleView(APIView):
    """
    Handles Activation and Deactivation.
    - Superusers: Full access to toggle any user.
    - Admins: Can only toggle 'staff' they personally created.
    """
    permission_classes = [IsAdminOrSuperuser, IsAccountActive]

    def post(self, request, user_id, action):
        target_user = get_object_or_404(CustomUser, id=user_id)
        
        # 1. Permission Check
        if request.user.role != 'superuser':
            # Admins cannot deactivate other Admins or Superusers
            if target_user.role != 'staff' or target_user.created_by != request.user:
                return error_response("Unauthorized: You can only manage your own staff members.", 403)

        # 2. Prevent Self-Lockout
        if target_user == request.user:
            return error_response("You cannot deactivate your own account.", 400)

        # 3. Apply Action
        if action == "activate":
            target_user.is_active = True
            message = f"User {target_user.username} has been activated."
        elif action == "deactivate":
            target_user.is_active = False
            message = f"User {target_user.username} has been deactivated. Access revoked."
        else:
            return error_response("Invalid action. Use 'activate' or 'deactivate'.", 400)

        target_user.save()

        return success_response(
            message, 
            data={"user_id": str(target_user.id), "is_active": target_user.is_active}
        )


class UpdateFCMTokenView(APIView):
    permission_classes = [IsAuthenticated,IsAccountActive]
    def post(self, request):
        token = request.data.get('fcm_token')
        request.user.fcm_token = token
        request.user.save()
        return Response({"status": "success", "message": "FCM Token Updated"})

class UserDashboardView(APIView):
    permission_classes = [IsAuthenticated,IsAccountActive]

    def get(self, request):
        try:
            user = request.user
            
            # 1. Role Detection
            role = 'superuser' if user.is_superuser else getattr(user, 'role', 'staff')
            if not role: role = 'staff'

            # 2. ✅ Location Detection with Default Fallback
            # If user.location is null, we return a default "Unassigned" or "Main" location
            if hasattr(user, 'location') and user.location:
                location_data = {
                    "id": user.location.id,
                    "name": user.location.name
                }
            else:
                location_data = {
                    "id": 0,
                    "name": "Default Location" # You can change this to "General" or "Office"
                }

            data = {
                "user": {
                    "username": user.username,
                    "user_id": user.id,
                    "role": role,
                    "name": getattr(user, 'name', user.username) or user.username,
                    "fcm_status": bool(getattr(user, 'fcm_token', None)),
                    "location": location_data
                }
            }

            return Response({
                "success": True,
                "data": data
            }, status=200)

        except Exception as e:
            print(f"--- DASHBOARD ERROR: {str(e)} ---")
            return Response({"success": False, "message": str(e)}, status=500)

class CheckUsernameAvailability(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckUsernameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exists = CustomUser.objects.filter(
            username__iexact=serializer.validated_data["username"]
        ).exists()

        return success_response(
            "Username availability checked",
            data={"available": not exists}
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = authenticate(
            request,
            username=request.data.get("login"),
            password=request.data.get("password")
        )

        if not user:
            return error_response("Invalid credentials", 401)

        refresh = RefreshToken.for_user(user)
        return success_response(
            "Login successful",
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }
        )




##########################################################################################################
######################################################################################################




# ---------- SIGNUP FLOW ----------

class SendSignupOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp = generate_otp()

        OTP.objects.update_or_create(
            email=request.data.get("email"),
            phone_number=request.data.get("phone_number"),
            purpose="signup",
            defaults={"otp": otp, "verified": False}
        )

        if request.data.get("email"):
            send_otp_email(request.data["email"], otp)

        return success_response("OTP sent successfully")

class VerifySignupOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email") or None
        phone = serializer.validated_data.get("phone_number") or None
        otp = serializer.validated_data["otp"]

        query = Q(otp=otp, purpose="signup")

        if email:
            query &= Q(email=email)
        elif phone:
            query &= Q(phone_number=phone)
        else:
            return error_response("Email or phone required", 400)

        otp_obj = OTP.objects.filter(query).first()

        if not otp_obj:
            return error_response("Invalid OTP", 400)

        if otp_obj.is_expired():
            otp_obj.delete()
            return error_response("OTP expired", 400)

        otp_obj.verified = True
        otp_obj.save()

        return success_response("OTP verified")


class CompleteSignup(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CompleteSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp_obj = OTP.objects.filter(
            verified=True,
            purpose="signup"
        ).filter(
            Q(email=serializer.validated_data.get("email")) |
            Q(phone_number=serializer.validated_data.get("phone_number"))
        ).first()

        if not otp_obj:
            return error_response("OTP not verified")

        user = CustomUser.objects.create_user(
            username=serializer.validated_data["username"],
            email=serializer.validated_data.get("email"),
            phone_number=serializer.validated_data.get("phone_number"),
            password=serializer.validated_data["password"],
            is_verified=True,
            is_password_set=True,
        )

        # Save as recovery contact
        if user.email:
            RecoveryContact.objects.create(
                user=user,
                contact_type="email",
                contact_value=user.email,
                is_verified=True
            )

        if user.phone_number:
            RecoveryContact.objects.create(
                user=user,
                contact_type="phone",
                contact_value=user.phone_number,
                is_verified=True
            )

        otp_obj.delete()

        refresh = RefreshToken.for_user(user)
        return success_response(
            "Signup completed",
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }
        )


# ---------- FORGOT PASSWORD ----------

class ForgotPasswordSendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recovery = RecoveryContact.objects.filter(
            contact_value=serializer.validated_data["contact"],
            is_verified=True
        ).select_related("user").first()

        if recovery:
            otp = generate_otp()
            OTP.objects.create(
                user=recovery.user,
                otp=otp,
                purpose="password_reset"
            )

            if recovery.contact_type == "email":
                send_otp_email(recovery.contact_value, otp)

        return success_response("If contact exists, OTP sent")


class ForgotPasswordVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        contact = serializer.validated_data["contact"]
        otp_input = serializer.validated_data["otp"]

        recovery = RecoveryContact.objects.filter(
            contact_value=contact,
            is_verified=True
        ).select_related("user").first()

        if not recovery:
            return error_response("Invalid contact", status_code=400)

        otp_obj = OTP.objects.filter(
            user=recovery.user,
            otp=otp_input,
            purpose="password_reset",
            verified=False
        ).first()

        if not otp_obj:
            return error_response("Invalid OTP", status_code=400)

        if otp_obj.is_expired():
            otp_obj.delete()
            return error_response("OTP expired", status_code=400)

        otp_obj.verified = True
        otp_obj.save()

        return success_response("OTP verified successfully")

class ForgotPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp_obj = OTP.objects.filter(
            otp=serializer.validated_data["otp"],
            purpose="password_reset",
            verified=True
        ).first()

        if not otp_obj or otp_obj.is_expired():
            return error_response("Invalid or expired OTP", status_code=400)

        user = otp_obj.user
        user.set_password(serializer.validated_data["new_password"])
        user.is_password_set = True
        user.save()

        otp_obj.delete()

        return success_response("Password reset successful")
