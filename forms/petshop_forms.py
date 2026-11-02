"""
forms/petshop_forms.py
Facade module tái xuất toàn bộ các Form cho hệ thống Pet Shop.
Tất cả các form được tách nhỏ theo nguyên tắc Single Responsibility:
- BaseFlaskForm: forms.base_form
- ProductForm: forms.product_forms
- SpaBookingForm, CheckoutForm, AdminLoginForm, NetworkApiForm: forms.customer_forms
"""

from forms.base_form import BaseFlaskForm
from forms.customer_forms import (
    AdminLoginForm,
    CheckoutForm,
    NetworkApiForm,
    SpaBookingForm,
)
from forms.product_forms import ProductForm

__all__ = [
    "BaseFlaskForm",
    "SpaBookingForm",
    "CheckoutForm",
    "ProductForm",
    "AdminLoginForm",
    "NetworkApiForm",
]
