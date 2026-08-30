# Data feasibility audit

## Decision

The project uses real monthly water-consumption observations from the City of Helsinki's open Nuuka API, catalogued by Helsinki Region Infoshare (HRI), for eight municipal school/service properties. The bounded study panel covers January 2010 through December 2018 and contains a complete 108-month sequence for every selected property.

This is property-level public-building consumption, not total HSY network demand and not a district-metered water-distribution zone. The title “Helsinki Water” refers to Helsinki municipal properties. No result is generalized to all Helsinki households or HSY's supply network.

## Sources checked

1. **HSY basic water-supply operations data.** Official HRI metadata says the series begins in 2010 but is annual. That is useful context but too short and too coarse for the requested rolling forecasting and uncertainty evaluation.
2. **HSY water service-area geodata.** Official polygons describe service coverage, not consumption through time.
3. **HRI / City of Helsinki Nuuka Open API.** The API is open without authentication and exposes Water, Electricity, Heat and DistrictCooling at monthly, daily and hourly endpoints where the underlying meter supports them. The provider warns that availability and validation quality vary by property and time.
4. **HEKA Energy and Climate Atlas water data.** The public resource contains annual observations for 2015–2018, insufficient for the requested forecasting design.
5. **FMI weather and sea observations.** These are real and usable external sources, but were not added to v1: the selected question is deliberately univariate so that the incremental evidence is time-series validation, uncertainty and decision optimization rather than another weather join already demonstrated elsewhere in the portfolio.

## Empirical API audit

The Nuuka monthly `Water` query for location names containing `koulu` returned 65 properties over 2010–2025. The audit initially identified 21 properties with exactly 108 distinct calendar months for 2010–2018, no duplicate month, no zero, no negative value and the declared `M3` unit. A repeated acquisition showed that one candidate no longer returned its 2018 records, so the validation gate rejected it and it was replaced before modeling. The final eight all pass the same complete-panel contract and provide geographic spread plus a tractable inspection portfolio.

Data after 2018 were not silently appended. The audit found irregular billing timestamps, missing calendar months and, in some properties, daily values repeated across billing intervals. Mixing those regimes with the clean 2010–2018 monthly panel would make the sample look newer while weakening the measurement contract.

## Reproducibility and license

- Catalog: https://hri.fi/data/en_GB/dataset/helsingin-kaupungin-palvelukiinteistojen-energiankulutustietoja
- API: https://helsinki-openapi.nuuka.cloud/swagger
- Maintainer: City of Helsinki Urban Environment Division / Built Assets Management
- License: Creative Commons Attribution 4.0

The acquisition command stores ignored raw responses, writes a compact versioned curated panel, and records SHA-256 hashes for raw and processed content. The committed curated subset is included so the published metrics remain reproducible if the live API later revises historical records.

The API was also observed to omit some 2018 records when the query itself ended in 2018, even though the same records were returned by a fixed wider query through 2025. Acquisition therefore downloads that wider immutable request window, filters the declared 2010–2018 panel locally and fails validation unless every selected property has exactly the expected 108 months. This guards the experiment from a silent server-side range quirk.
