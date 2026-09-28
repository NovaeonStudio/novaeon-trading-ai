# Labeling guide: novaeon-kev crypto news judgments (teacher labels)

Each item: one coin + its recent headlines (newest first, age in hours). Answer the two questions the live
trading bot asks before buying that coin. Judge ONLY what the headlines say, about THIS coin.

## major_negative (true/false)
"Do these headlines report a major negative event specifically for COIN that makes buying it now dangerous?"
- TRUE only for a concrete, serious, coin-specific event that is reported as having happened or being underway:
  hack/exploit/theft of this chain/protocol or its bridge, delisting from a major exchange, regulator action or
  lawsuit AGAINST this project/issuer, insolvency, chain halt/outage, founder/team arrest, confirmed large
  coordinated sell-off/unlock dump of this coin.
- FALSE for: price predictions and "could crash" speculation, clickbait questions, general market dips,
  another project's hack where this coin is only mentioned (e.g. "X switches to Chainlink after exploit" is
  NOT negative for Chainlink), old resolved matters framed as history, analyst opinions, ETF delays that are routine.
- If several headlines conflict, TRUE if at least one concrete serious coin-specific negative event is reported.

## outlook (clearly_positive / neutral_or_mixed / negative)
- clearly_positive: concrete, material good news for this coin itself (major adoption/partnership actually
  announced, ETF/listing approval, large confirmed inflows, major upgrade shipped). NOT price-target hype.
- negative: material bad news or risk for this coin (includes every major_negative=true case, plus serious but
  less acute risks like a regulator probe opened, a large token unlock announced, a major outage).
- neutral_or_mixed: everything else: price commentary, predictions, "should you buy", passing mentions,
  mixed good/bad, routine updates.
- Be conservative: when unsure between clearly_positive and neutral_or_mixed, choose neutral_or_mixed.

## Round 2 (v2): four extra questions, answer them for EVERY item

### event_type (pick ONE: the most important kind of news about THIS coin)
security_incident · exchange_delisting · legal_regulatory_negative · legal_regulatory_positive · etf_or_listing ·
adoption_partnership · tech_upgrade · supply_flow · price_commentary · not_about_coin
- Exact definitions are in `questions_v2.py` (EVENT_TYPES). If nothing concrete happened, it is price_commentary;
  if the coin is only mentioned in passing everywhere, it is not_about_coin.
- Must be consistent with the other answers: major_negative=true usually means security_incident,
  exchange_delisting or legal_regulatory_negative (or supply_flow for a real dump).

### impact (integer 0-4: how strongly could this move THIS coin's price in the next few days, either direction)
0 none (nothing material about this coin) · 1 minor · 2 moderate · 3 major · 4 extreme (existential / once-a-year).
- Routine partnership = 1; ETF approval/launch or large exchange delisting = 3; chain-breaking hack or counterfeit
  bug = 4. Price commentary alone = 0 or 1.

### relevant (true/false): is at least one headline actually ABOUT this coin (not a passing mention)?

### stale (true/false): is the most important news old/resolved (rehash, recap, anniversary, follow-up opinion)
rather than a new development? false when nothing notable is reported.
