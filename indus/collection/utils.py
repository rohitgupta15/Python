from django.contrib.auth.decorators import user_passes_test


def group_required(*group_names):
    def in_groups(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=group_names).exists()

    return user_passes_test(in_groups)
