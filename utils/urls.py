"""
URL configuration for utils app.
"""
from django.urls import path
from . import views

app_name = 'utils'

urlpatterns = [
    path('currency/rates/', views.get_currency_rates, name='currency-rates'),
    path('currency/supported/', views.get_supported_currencies, name='supported-currencies'),
]
