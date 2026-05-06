{
    'name': 'NFC AI Insight',
    'version': '18.0.1.3.0',
    'summary': 'AI Decision Insight cho Purchase Order — NFC',
    'category': 'Purchase',
    'author': 'NFC',
    'depends': ['purchase', 'web', 'nfc_purchase_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/purchase_request_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nfc_ai_insight/static/src/services/ai_service.js',
            'nfc_ai_insight/static/src/components/sparkline.js',
            'nfc_ai_insight/static/src/xml/sparkline.xml',
            'nfc_ai_insight/static/src/components/multi_line_chart_field.js',
            'nfc_ai_insight/static/src/components/nfc_version.js',
            'nfc_ai_insight/static/src/components/insight_badge.js',
            'nfc_ai_insight/static/src/xml/insight_badge.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
