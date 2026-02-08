

def get_user_organisation(user):
    """
    Returns organisation for logged-in user.
    Assumes OrganisationUser exists.
    """
    return user.organisation_user.organisation
