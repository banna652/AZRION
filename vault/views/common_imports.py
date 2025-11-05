from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from ..models import User, Category, Product, Address, Order, Cart, CartItem, Wishlist, WishlistItem, OrderItem, ProductVariant, ReturnRequest, ItemReturnRequest, CouponUsage, Coupon, ReferralReward, ReferralOffer, Wallet, WalletTransaction, ProductReview
from django.db.models import Q
from django.db import models
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import random
import re
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import get_template
from io import BytesIO
from xhtml2pdf import pisa
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import razorpay
import hmac
import hashlib
import logging
from decimal import Decimal
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.conf.urls import handler404


logger = logging.getLogger(__name__)

try:
    if hasattr(settings, 'RAZORPAY_KEY_ID') and hasattr(settings, 'RAZORPAY_KEY_SECRET'):
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            logger.info("Razorpay client initialized successfully")
        else:
            razorpay_client = None
            logger.error("Razorpay keys are empty")
    else:
        razorpay_client = None
        logger.error("Razorpay keys not found in settings")
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay client: {e}")

def generate_otp():
    return str(random.randint(100000, 999999))

def check_user_blocked(user):
    if user.is_authenticated and not user.is_active and not user.is_staff:
        return True
    return False