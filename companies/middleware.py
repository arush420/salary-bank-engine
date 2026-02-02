# middleware.py
from companies.models import Company, OrganisationUser


class CompanyContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # SAFE DEFAULTS
        request.role = None
        request.organisation = None
        request.available_companies = []

        if request.user.is_authenticated:
            org_user = (
                OrganisationUser.objects
                .select_related("organisation")
                .filter(user=request.user)
                .first()
            )

            if org_user:
                request.role = org_user.role
                request.organisation = org_user.organisation

                request.available_companies = (
                    Company.objects
                    .filter(
                        organisation=org_user.organisation,
                        is_active=True
                    )
                    .order_by("serial_no")
                )

        return self.get_response(request)
