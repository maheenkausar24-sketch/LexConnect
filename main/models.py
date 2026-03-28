from django.db import models
from django.contrib.auth.models import User


class LawCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Lawyer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)

    # 🔥 CONNECT CATEGORY
    category = models.ForeignKey('LawCategory', on_delete=models.CASCADE)

    specialization = models.CharField(max_length=100)
    experience = models.IntegerField()
    location = models.CharField(max_length=100)

    def __str__(self):
        return self.name



class Message(models.Model):

    chat = models.ForeignKey("ChatSession", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)

    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)


from django.db import models


# ✅ Lawyer Model (FIRST)
class Lawyer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    experience = models.IntegerField()
    location = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ✅ Chat Session
class ChatSession(models.Model):
    user_name = models.CharField(max_length=100)
    lawyer = models.ForeignKey('main.Lawyer', on_delete=models.CASCADE, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.user_name


# ✅ Consultation
class Consultation(models.Model):
    lawyer = models.ForeignKey('main.Lawyer', on_delete=models.CASCADE)
    client_name = models.CharField(max_length=100)
    issue = models.TextField()

    def __str__(self):
        return self.client_name


# ✅ Review
class Review(models.Model):
    lawyer = models.ForeignKey('main.Lawyer', on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return str(self.rating)