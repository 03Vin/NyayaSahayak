from django import forms
from datetime import date


class NoticeGuidedForm(forms.Form):
    notice_date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Notice Date"
    )
    sender_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ramesh Kumar'}),
        label="Your Full Name (Sender / Claimant)"
    )
    sender_address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Your complete postal address with PIN code'}),
        label="Your Postal Address"
    )
    recipient_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Landlord Name / Company Name / Employer Name'}),
        label="Opposing Party Full Name (Recipient)"
    )
    recipient_address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Complete address of the opposing party / company registered office'}),
        label="Opposing Party Address"
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date Due / Dispute Inception Date",
        help_text="For wages claims, the date wages fell due determines whether Code on Wages (2019) or older repealed acts apply."
    )
    facts = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'State what happened in chronological order: dates, agreements signed, amount paid, transaction numbers, defects noticed, or non-payment.'
        }),
        label="Chronological Facts of the Dispute"
    )
    relief_demanded = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Specific demand: e.g. "Refund of security deposit of Rs 35,000 within 15 days", "Payment of arrears of Rs 48,000", or "Replacement of defective refrigerator".'
        }),
        label="Specific Relief Demanded & Compliance Window"
    )

