from django import forms
from django.core.exceptions import ValidationError
from catalogue.models import Product, Category, SubCategory

class AuditInitiateForm(forms.Form):
    SCOPE_CHOICES = [
        ('all', 'All Stock'),
        ('category', 'Category'),
        ('subcategory', 'Sub-Category'),
    ]
    scope = forms.ChoiceField(choices=SCOPE_CHOICES, required=True)
    sample_size = forms.IntegerField(required=False)
    category_id = forms.UUIDField(required=False)
    subcategory_id = forms.UUIDField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        scope = cleaned_data.get('scope')
        sample_size = cleaned_data.get('sample_size')
        category_id = cleaned_data.get('category_id')
        subcategory_id = cleaned_data.get('subcategory_id')

        if scope == 'all':
            # Skip sample_size validation/requirements
            return cleaned_data

        if sample_size is None:
            self.add_error('sample_size', 'Sample size is required for category/subcategory scopes.')
            return cleaned_data

        # Determine target product count
        qs = Product.objects.filter(is_active=True)
        if scope == 'category':
            if not category_id:
                self.add_error('category_id', 'Category is required.')
                return cleaned_data
            qs = qs.filter(subcategory__category_id=category_id)
            total_count = qs.count()
            if total_count == 0:
                self.add_error('category_id', 'No active products found in this category.')
            elif sample_size < 1 or sample_size > total_count:
                self.add_error('sample_size', f'Sample size must be between 1 and the total number of active products in this category ({total_count}).')
        elif scope == 'subcategory':
            if not subcategory_id:
                self.add_error('subcategory_id', 'Sub-Category is required.')
                return cleaned_data
            qs = qs.filter(subcategory_id=subcategory_id)
            total_count = qs.count()
            if total_count == 0:
                self.add_error('subcategory_id', 'No active products found in this sub-category.')
            elif sample_size < 1 or sample_size > total_count:
                self.add_error('sample_size', f'Sample size must be between 1 and the total number of active products in this sub-category ({total_count}).')

        return cleaned_data
