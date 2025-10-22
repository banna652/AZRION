from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from vault.models import User, Category, Product, ProductVariant, VariantImage, Order, ReturnRequest, ItemReturnRequest, Wallet, ReferralReward, CategoryOffer, ReferralOffer, Coupon, CouponUsage, OrderItem, WalletTransaction
from django.contrib import messages
from django.core.files.base import ContentFile
from io import BytesIO
from django.db.models import Q, Count, Sum
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.template.loader import get_template
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from xhtml2pdf import pisa
from django.utils import timezone
from datetime import datetime, timedelta
from PIL import Image
import re
from django.utils import timezone
from zoneinfo import ZoneInfo