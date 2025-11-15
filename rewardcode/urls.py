# rewardcodes/urls.py
from django.urls import path
from .views import RewardCodeListCreateView, RedeemCodeView

urlpatterns = [
    path('rewardcodes/', RewardCodeListCreateView.as_view(), name='rewardcodes-list-create'),
    path('rewardcodes/redeem/', RedeemCodeView.as_view(), name='rewardcodes-redeem'),
]