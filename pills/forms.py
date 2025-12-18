from django import forms
from .models import Thread, Comment

class ThreadForm(forms.ModelForm):
    reading_date = forms.DateField(
        label='영양제 복용일',
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'date'
        })
    )
    class Meta:
        model = Thread
        exclude = ["cover_img", "likes", "user", "pill", "created_at", "updated_at"]

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        exclude = ('user', 'thread', "created_at", "updated_at")