"""Question set for Novaeon Kev v2: the two live questions (unchanged wording, see BreakoutRegimeKev._assess) plus
four new typed questions the bot can use later. Keep in sync with the strategy when a new question goes live."""

EVENT_TYPES = {
    "security_incident": "Hack, exploit, theft, critical bug, or an outage/chain halt of this coin's chain or protocol.",
    "exchange_delisting": "A major exchange or broker delists it or restricts trading/deposits of it.",
    "legal_regulatory_negative": "Regulator action, probe, lawsuit, ban or court order against this project or issuer.",
    "legal_regulatory_positive": "A probe closed, lawsuit won/settled, or regulatory clarity/approval in its favour.",
    "etf_or_listing": "ETF/ETP launch or approval, new major exchange listing, futures listing.",
    "adoption_partnership": "Concrete adoption, integration, partnership or institutional use actually announced.",
    "tech_upgrade": "Upgrade, mainnet or major product feature shipped (not just planned).",
    "supply_flow": "Token unlock, large whale/team selling, buybacks, or large confirmed fund inflows/outflows.",
    "price_commentary": "Price moves, predictions, technical analysis, 'should you buy' pieces.",
    "not_about_coin": "The headlines are about something else; the coin is only mentioned in passing or not at all.",
}


def questions(coin: str) -> dict:
    return {
        # --- live today (identical wording to the strategy) ---
        "major_negative": {
            "type": "noul",
            "instructions": f"Do these headlines report a major negative event specifically for {coin} "
                            "that makes buying it now dangerous?",
            "criteria": {
                "true": "Hack or exploit, delisting, regulatory action or lawsuit against it, insolvency, "
                        "chain halt, founder arrest, or a large coordinated sell-off of this coin.",
                "false": "Neutral or positive news, general market commentary, price analysis, or news "
                         "that only mentions the coin in passing.",
            },
        },
        "outlook": {
            "type": "choice",
            "instructions": f"Overall, how do these headlines bear on {coin} specifically over the next few days?",
            "criteria": {
                "clearly_positive": f"Concrete, material good news for {coin} itself: major adoption or "
                                    "partnership, ETF or listing approval, strong inflows, upgrade shipped.",
                "neutral_or_mixed": "Routine news, price commentary, mixed signals, or the coin is only "
                                    "mentioned in passing.",
                "negative": f"Material bad news or risk for {coin}.",
            },
        },
        # --- new in v2 ---
        "event_type": {
            "type": "choice",
            "instructions": f"What is the single most important kind of news about {coin} in these headlines?",
            "criteria": EVENT_TYPES,
        },
        "impact": {
            "type": "score",
            "instructions": f"How strongly could these headlines move {coin}'s price over the next few days, "
                            "in either direction?",
            "criteria": ["none: nothing material about this coin", "minor", "moderate", "major",
                         "extreme: existential or once-a-year event for this coin"],
        },
        "relevant": {
            "type": "noul",
            "instructions": f"Is at least one of these headlines actually about {coin} itself, rather than "
                            "mentioning it in passing?",
        },
        "stale": {
            "type": "noul",
            "instructions": f"Is the most important news here about {coin} old or already resolved (a rehash, "
                            "anniversary, follow-up commentary or recap), rather than a new development?",
        },
    }
