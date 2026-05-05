{
    'name': 'NFC AI Insight',
    'version': '18.0.1.0.0',
    'summary': 'AI Decision Insight cho Purchase Order — NFC',
    'category': 'Purchase',
    'author': 'NFC',
    'depends': ['purchase', 'web', 'nfc_purchase_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nfc_ai_insight/static/src/services/ai_service.js',
            'nfc_ai_insight/static/src/components/insight_badge.js',
            'nfc_ai_insight/static/src/xml/insight_badge.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
