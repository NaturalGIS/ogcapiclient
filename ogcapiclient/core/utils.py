"""Utilities and helpers."""

from ogcapiclient.core.models import Link


def parse_links(links: list[dict]) -> list[Link]:
    """Parses the links JSON object into a list of Link objects.

    :param links:
    :type links: list[dict]

    :returns: A list of parsed Link objects.
    :rtype: list[Link]
    """
    parsed_links: list[Link] = []

    if not isinstance(links, list):
        return parsed_links

    for i in links:
        if not isinstance(i, dict):
            continue

        link = Link(
            href=str(i.get("href", "")),
            rel=str(i.get("rel", "")),
            type=str(i.get("type", "")),
            title=str(i.get("title", "")),
        )

        templated = i.get("templated")
        if isinstance(templated, bool):
            link.templated = templated

        length = i.get("length")
        if isinstance(length, (int, float)):
            link.length = int(length)

        profiles = i.get("profile")
        if isinstance(profiles, list):
            link.profiles = [str(p) for p in profiles]
        elif isinstance(profiles, str):
            link.profiles = [profiles]

        parsed_links.append(link)

    return parsed_links


def find_link(
    links: list[Link], rel: str, preferable_types: list[str] = []
) -> str | None:
    """Finds the href of the best-matching link.

     :param links: List of parsed links.
     :type links: list[Link]
    :param rel: The rel value to match.
    :type rel: str
    :param preferable_types: Ordered list of preferred MIME types.
    :type preferable_types: list[str]

    :returns: The URL of the best match or an empty string.
    :rtype: str, None

    """
    if preferable_types is None:
        preferable_types = []

    best_href = None
    best_priority = float("inf")

    for link in links:
        if link.rel == rel:
            priority = (
                preferable_types.index(link.type)
                if link.type in preferable_types
                else len(preferable_types)
            )

            if priority < best_priority:
                best_href = link.href
                best_priority = priority
    return best_href
