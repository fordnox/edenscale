"""Shared LP-visibility query fragments.

LP (investor) reads are keyed off ``InvestorContact.user_id`` linkage.
These helpers scope that linkage to the active membership's organization
so a contact binding in one organization can never be exercised through
a membership in another.
"""

from sqlalchemy import Select, select

from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership


def lp_visible_investor_ids(membership: UserOrganizationMembership) -> Select:
    """Investor ids the membership's user is a linked contact for,
    restricted to the membership's organization."""
    return (
        select(InvestorContact.investor_id)
        .join(Investor, Investor.id == InvestorContact.investor_id)
        .where(
            InvestorContact.user_id == membership.user_id,
            Investor.organization_id == membership.organization_id,
        )
    )


def lp_visible_contact_ids(membership: UserOrganizationMembership) -> Select:
    """Contact ids linked to the membership's user, restricted to the
    membership's organization."""
    return (
        select(InvestorContact.id)
        .join(Investor, Investor.id == InvestorContact.investor_id)
        .where(
            InvestorContact.user_id == membership.user_id,
            Investor.organization_id == membership.organization_id,
        )
    )
