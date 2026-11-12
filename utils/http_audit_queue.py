"""Path boundaries shared by HTTP collection, historical payload disclosure and cleanup."""

AI_ROOTS = ('/assistant', '/admin/ai', '/api/ai', '/internal/ai', '/api/admin/ai')


def protected_path(path):
    """Include unmatched URLs inside an AI namespace, using complete path segments."""
    return any(path == root or path.startswith(root + '/') for root in AI_ROOTS)


def cleanup_filter():
    """SQLite GLOB keeps the same case-sensitive segment boundaries as protected_path."""
    terms = ['(RequestPath != ? AND RequestPath NOT GLOB ?)' for root in AI_ROOTS]
    values = tuple(value for root in AI_ROOTS for value in (root, root + '/*'))
    return ' AND '.join(terms), values


def payload_visible(path):
    """The detail route and list flags use the same historical privacy policy."""
    return (not protected_path(path) and path.startswith('/api/')
            and not path.startswith(('/api/auth/', '/api/admin/maintenance/', '/api/maintenance/', '/api/admin/database/'))
            and path not in ('/api/change_password', '/api/users/update_email', '/api/users/update_profile', '/api/users/withdraw')
            and not path.endswith('/reset_password'))
