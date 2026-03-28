from django.urls import path
from . import views

urlpatterns = [

    path('', views.home, name='home'),

    path('register/', views.register, name='register'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_user, name='logout'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('chatbot/', views.chatbot, name='chatbot'),
    path('ask-lexora/', views.ask_lexora, name='ask_lexora'),

    path('lawyers/<int:category_id>/', views.lawyers_by_category, name='lawyers_by_category'),

    path('consult/<int:lawyer_id>/', views.consult_lawyer, name='consult_lawyer'),

    path("chat/start/<int:consultation_id>/", views.start_chat, name="start_chat"),

    path("chat/<int:consultation_id>/", views.consultation_chat, name="consultation_chat"),  # ← FIXED

    path("lawyer/register/", views.lawyer_register, name="lawyer_register"),
    path("lawyer/login/", views.lawyer_login, name="lawyer_login"),
    path("lawyer/dashboard/", views.lawyer_dashboard, name="lawyer_dashboard"),
    path("lawyer/profile/<int:lawyer_id>/", views.lawyer_profile, name="lawyer_profile"),
    path("request-success/", views.request_success, name="request_success"),
    path("chat/<int:chat_id>/", views.chat_page, name="chat_page"),  
    path("my-chats/", views.user_chats, name="user_chats")

]