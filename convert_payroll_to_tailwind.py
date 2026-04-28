import os

FILE_PATH = 'payroll/templates/payroll/period_detail.html'

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove DOCTYPE, html, head, body tags
content = content.replace('<!DOCTYPE html>', '{% extends "base.html" %}\n{% block content %}')
import re
content = re.sub(r'<html.*?>', '', content)
content = re.sub(r'<head>.*?</head>', '', content, flags=re.DOTALL)
content = content.replace('<body>', '')
content = content.replace('</body>', '')
content = content.replace('</html>', '{% endblock %}')

# Basic Grid
content = content.replace('container-fluid mt-4', 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 safe-bottom')
content = content.replace('row', 'flex flex-wrap -mx-4')
content = content.replace('col-md-8', 'w-full md:w-2/3 px-4')
content = content.replace('col-md-4', 'w-full md:w-1/3 px-4')
content = content.replace('col-md-3', 'w-full md:w-1/4 px-4')
content = content.replace('col-md-6', 'w-full md:w-1/2 px-4')

# Margins and Paddings
content = content.replace('mb-4', 'mb-4')
content = content.replace('mb-2', 'mb-2')
content = content.replace('mb-0', 'mb-0')
content = content.replace('me-2', 'mr-2')
content = content.replace('me-3', 'mr-3')
content = content.replace('mt-4', 'mt-4')
content = content.replace('p-0', 'p-0')
content = content.replace('g-4', 'gap-4')
content = content.replace('py-4', 'py-4')
content = content.replace('px-6', 'px-6')

# Flexbox
content = content.replace('align-items-center', 'items-center')
content = content.replace('d-flex', 'flex')
content = content.replace('d-block', 'block')
content = content.replace('text-end', 'text-right')
content = content.replace('text-center', 'text-center')
content = content.replace('d-inline', 'inline-block')

# Typography
content = content.replace('fw-bold', 'font-bold')
content = content.replace('text-muted', 'text-text-secondary')
content = content.replace('text-success', 'text-emerald-500')
content = content.replace('text-danger', 'text-red-500')
content = content.replace('text-warning', 'text-amber-500')
content = content.replace('text-primary', 'text-[var(--primary)]')
content = content.replace('text-info', 'text-cyan-500')
content = content.replace('fs-4', 'text-2xl')
content = content.replace('fs-2', 'text-4xl')
content = content.replace('fs-6', 'text-sm')

# Components
content = content.replace('card-body', 'p-6')
content = content.replace('table-responsive', 'overflow-x-auto')
content = content.replace('table-striped', 'divide-y divide-[var(--border)]')
content = content.replace('table-dark', 'bg-gray-50/50 text-text-secondary uppercase text-xs tracking-wider')
content = content.replace('bg-white rounded-lg shadow-md overflow-hidden', 'card overflow-hidden')

# Modals
content = content.replace('modal fade', 'fixed inset-0 z-50 flex items-center justify-center bg-black/50 hidden')
content = content.replace('modal-dialog modal-dialog-centered', 'bg-white rounded-2xl w-full max-w-lg mx-4 shadow-2xl')
content = content.replace('modal-content', 'overflow-hidden')
content = content.replace('modal-header', 'px-6 py-4 border-b border-[var(--border)] flex justify-between items-center')
content = content.replace('modal-title', 'text-lg font-bold text-text-primary')
content = content.replace('modal-body', 'p-6')
content = content.replace('modal-footer', 'px-6 py-4 bg-gray-50 flex justify-end gap-3 border-t border-[var(--border)]')
content = content.replace('btn-close btn-close-white', 'text-white hover:text-gray-200')
content = content.replace('form-label', 'block text-sm font-bold text-text-primary mb-1.5')
content = content.replace('form-control', 'w-full bg-gray-50 border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm font-medium text-text-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-all')

# Fix tables
content = content.replace('<table class="', '<table class="w-full text-left border-collapse ')
content = content.replace('<tr>\n                  <th>', '<tr class="border-b border-[var(--border)]">\n                  <th class="py-4 px-6">')
content = content.replace('<th>', '<th class="py-4 px-6">')
content = content.replace('<td>', '<td class="py-4 px-6 text-sm">')

# Custom badging
content = content.replace('badge bg-light text-dark', 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-gray-100 text-gray-800')

with open(FILE_PATH, 'w', encoding='utf-8') as f:
    f.write(content)
