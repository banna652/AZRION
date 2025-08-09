from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import uuid
import string
import random

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if not password:
            raise ValueError('Superusers must have a password.')
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(max_length=50)
    ph_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    pro_image = models.ImageField(upload_to='profile_images/', blank=True, null=True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    
    # Referral system fields
    referral_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    referral_token = models.UUIDField(default=uuid.uuid4, unique=True)


    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    def generate_referral_code(self):
        """Generate a unique referral code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not User.objects.filter(referral_code=code).exists():
                return code

    def get_referral_url(self):
        """Get referral URL with token"""
        from django.urls import reverse
        return reverse('register_with_referral', kwargs={'token': str(self.referral_token)})

class Address(models.Model):
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='home')
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.address_type}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_active_offer(self):
        """Get the currently active category offer"""
        now = timezone.now()
        return self.category_offers.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).first()

    def get_offer_percentage(self):
        """Get current offer percentage for this category"""
        offer = self.get_active_offer()
        return offer.discount_percentage if offer else 0

class CategoryOffer(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_offers')
    offer_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.offer_name} - {self.category.name} ({self.discount_percentage}%)"

    def is_valid(self):
        """Check if offer is currently valid"""
        now = timezone.now()
        return (self.is_active and 
                self.valid_from <= now <= self.valid_until)

    def clean(self):
        if self.discount_percentage < 0 or self.discount_percentage > 100:
            raise ValidationError("Discount percentage must be between 0 and 100")
        if self.valid_from >= self.valid_until:
            raise ValidationError("Valid from date must be before valid until date")

class Product(models.Model):
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    product_name = models.CharField(max_length=100, unique=True)
    product_description = models.TextField(blank=True, null=True)
    price = models.PositiveIntegerField()
    product_offer = models.FloatField(default=0.0)
    main_image = models.ImageField(upload_to='product_main_images/', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    def get_main_image(self):
        if self.main_image:
            return self.main_image
        first_variant = self.variants.first()
        if first_variant:
            first_image = first_variant.images.first()
            if first_image:
                return first_image.image
        return None

    def get_total_variants(self):
        return self.variants.count()

    def get_average_rating(self):
        from django.db.models import Avg
        avg_rating = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 1) if avg_rating else 0

    def get_total_reviews(self):
        return self.reviews.count()

    def get_rating_distribution(self):
        from django.db.models import Count
        distribution = {}
        for i in range(1, 6):
            count = self.reviews.filter(rating=i).count()
            distribution[i] = count
        return distribution

    def get_total_stock(self):
        return sum(variant.stock_quantity for variant in self.variants.all())

    def is_available(self):
        return not self.is_deleted and self.get_total_stock() > 0

    def get_best_offer_percentage(self):
        """Get the best offer percentage between product and category offers"""
        product_offer = self.product_offer
        category_offer = self.category.get_offer_percentage()
        return max(float(product_offer), float(category_offer))

    def get_discounted_price(self):
        """Calculate discounted price using the best available offer"""
        best_offer = self.get_best_offer_percentage()
        if best_offer > 0:
            discount_amount = (self.price * best_offer) / 100
            return self.price - discount_amount
        return self.price

    def get_offer_details(self):
        """Get details about which offer is being applied"""
        product_offer = self.product_offer
        category_offer = self.category.get_offer_percentage()
        
        if product_offer > category_offer:
            return {
                'type': 'product',
                'percentage': product_offer,
                'source': 'Product Offer'
            }
        elif category_offer > 0:
            category_offer_obj = self.category.get_active_offer()
            return {
                'type': 'category',
                'percentage': category_offer,
                'source': f'Category Offer: {category_offer_obj.offer_name}' if category_offer_obj else 'Category Offer'
            }
        else:
            return {
                'type': 'none',
                'percentage': 0,
                'source': 'No Offer'
            }

class ProductVariant(models.Model):
    COLOR_CHOICES = [
        ('red', 'Red'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('black', 'Black'),
        ('white', 'White'),
        ('yellow', 'Yellow'),
        ('orange', 'Orange'),
        ('purple', 'Purple'),
        ('pink', 'Pink'),
        ('brown', 'Brown'),
        ('gray', 'Gray'),
        ('navy', 'Navy'),
        ('gold', 'Gold'),
        ('silver', 'Silver'),
        ('rose_gold', 'Rose Gold'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=20, choices=COLOR_CHOICES)
    color_code = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color code (e.g., #FF0000)")
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Available stock for this variant")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product.product_name} - {self.get_color_display()}"

    def get_image_count(self):
        return self.images.count()

    def is_in_stock(self):
        return self.stock_quantity > 0

    def get_stock_status(self):
        if self.stock_quantity == 0:
            return "Out of Stock"
        elif self.stock_quantity <= 5:
            return "Low Stock"
        else:
            return "In Stock"

class ProductReview(models.Model):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    review_text = models.TextField(blank=True, null=True)
    is_verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.product.product_name} ({self.rating} stars)"

class VariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='variant_images/')
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.variant}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            VariantImage.objects.filter(variant=self.variant, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

# Coupon Model (existing)
class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'percentage' else '₹'}"

    def is_valid(self, user=None, cart_total=0):
        """Check if coupon is valid for use"""
        now = timezone.now()
        
        # Check if coupon is active
        if not self.is_active:
            return False, "This coupon is not active."
        
        # Check date validity
        if now < self.valid_from:
            return False, "This coupon is not yet valid."
        
        if now > self.valid_until:
            return False, "This coupon has expired."
        
        # Check usage limit
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "This coupon has reached its usage limit."
        
        # Check minimum amount
        if cart_total < self.minimum_amount:
            return False, f"Minimum order amount of ₹{self.minimum_amount} required."
        
        # Check if user has already used this coupon
        if user and user.is_authenticated:
            if CouponUsage.objects.filter(user=user, coupon=self).exists():
                return False, "You have already used this coupon."
        
        return True, "Coupon is valid."

    def calculate_discount(self, cart_total):
        """Calculate discount amount for given cart total"""
        if self.discount_type == 'percentage':
            discount = (float(cart_total) * float(self.discount_value)) / 100
            if self.maximum_discount:
                discount = min(discount, self.maximum_discount)
        else:
            discount = self.discount_value
        
        # Ensure discount doesn't exceed cart total
        return min(discount, cart_total)

class ReferralOffer(models.Model):
    offer_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    reward_type = models.CharField(max_length=20, choices=[
        ('coupon', 'Coupon'),
        ('cashback', 'Cashback'),
    ], default='coupon')
    reward_value = models.DecimalField(max_digits=10, decimal_places=2)
    reward_type_detail = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], default='percentage')
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_referrals = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum referrals per user")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.offer_name} - {self.reward_value}{'%' if self.reward_type_detail == 'percentage' else '₹'}"

    def generate_referral_coupon(self, user):
        """Generate a coupon for successful referral"""
        if self.reward_type == 'coupon':
            coupon_code = f"REF{user.id}{random.randint(1000, 9999)}"
            
            # Calculate coupon validity (30 days from now)
            valid_from = timezone.now()
            valid_until = valid_from + timedelta(days=30)
            
            coupon = Coupon.objects.create(
                code=coupon_code,
                description=f"Referral reward: {self.offer_name}",
                discount_type=self.reward_type_detail,
                discount_value=self.reward_value,
                minimum_amount=self.minimum_order_amount,
                usage_limit=1,
                valid_from=valid_from,
                valid_until=valid_until,
                is_active=True
            )
            
            return coupon
        return None

class ReferralReward(models.Model):
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_rewards')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_rewards')
    referral_offer = models.ForeignKey(ReferralOffer, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_claimed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['referrer', 'referred_user']

    def __str__(self):
        return f"Referral reward for {self.referrer.full_name} (referred {self.referred_user.full_name})"

class CouponUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.CASCADE, null=True, blank=True)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'coupon']

    def __str__(self):
        return f"{self.user.email} used {self.coupon.code}"

class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('online', 'Online Payment'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    
    # Coupon fields
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order_number}"

    def can_be_cancelled(self):
        return any(item.can_be_cancelled() for item in self.items.all())

    def get_order_status(self):
        items = self.items.all()
        if not items:
            return self.status
        active_items = [item for item in items if item.status not in ['cancelled', 'returned']]
        if not active_items:
            cancelled_count = sum(1 for item in items if item.status == 'cancelled')
            returned_count = sum(1 for item in items if item.status == 'returned')
            if cancelled_count > returned_count:
                return 'cancelled'
            else:
                return 'returned'
        return self.status

# Cart Models
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    applied_coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.full_name}"

    def get_total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_subtotal(self):
        total = 0
        for item in self.items.all():
            total += item.get_total_price()
        return total

    def get_coupon_discount(self):
        if self.applied_coupon:
            subtotal = self.get_subtotal()
            return self.applied_coupon.calculate_discount(subtotal)
        return 0

    def get_total_price(self):
        subtotal = self.get_subtotal()
        discount = self.get_coupon_discount()
        return subtotal - discount

    def get_items_count(self):
        return self.items.count()

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cart', 'product', 'variant']

    def __str__(self):
        return f"{self.product.product_name} - {self.variant.get_color_display()} (x{self.quantity})"

    def get_total_price(self):
        return self.product.get_discounted_price() * self.quantity

    def get_unit_price(self):
        return self.product.get_discounted_price()

    def is_available(self):
        return (not self.product.is_deleted and 
                not self.product.category.is_deleted and 
                self.variant.is_active and 
                self.variant.stock_quantity >= self.quantity)

class Wishlist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wishlist')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist for {self.user.full_name}"

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['wishlist', 'product', 'variant']

    def __str__(self):
        return f"{self.product.product_name} - {self.variant.get_color_display()}"

class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.product_name} - {self.variant.get_color_display()} (x{self.quantity})"

    def get_total_price(self):
        return self.price * self.quantity

    def can_be_cancelled(self):
        return (self.status == 'active' and 
                self.order.status in ['pending', 'confirmed'] and
                not hasattr(self, 'return_request'))

    def can_be_returned(self):
        from datetime import timedelta
        from django.utils import timezone
        return (self.status == 'active' and 
                self.order.status == 'delivered' and
                not hasattr(self, 'return_request') and
                timezone.now() <= self.order.created_at + timedelta(days=7))

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user.full_name} - Balance: ₹{self.balance}"

    def add_money(self, amount, description=""):
        from decimal import Decimal
        amount = Decimal(str(amount))
        self.balance += amount
        self.save()
        WalletTransaction.objects.create(
            wallet=self,
            transaction_type='credit',
            amount=amount,
            description=description
        )
        return True

    def deduct_money(self, amount, description=""):
        from decimal import Decimal
        amount = Decimal(str(amount))
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            WalletTransaction.objects.create(
                wallet=self,
                transaction_type='debit',
                amount=amount,
                description=description
            )
            return True
        return False

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'), 
        ('debit', 'Debit'),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type.title()} - ₹{self.amount}"

class ItemReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), 
        ('approved', 'Approved'), 
        ('rejected', 'Rejected')
    ]
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='return_request')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_item_returns')

    def __str__(self):
        return f"Return Request for {self.order_item.product.product_name} in Order {self.order_item.order.order_number}"

class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), 
        ('approved', 'Approved'), 
        ('rejected', 'Rejected')
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='return_request')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_returns')

    def __str__(self):
        return f"Return Request for Order {self.order.order_number}"


