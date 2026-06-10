"""Country/continent/subdivision reference data and helpers (stdlib only)."""

CONTINENT_ORDER = [
    "Africa",
    "Antarctica",
    "Asia",
    "Europe",
    "North America",
    "Oceania",
    "South America",
    "Unknown",
]


def flag(iso2):
    """Return the regional-indicator flag emoji for a 2-letter ISO code."""
    if not iso2:
        return ""
    iso2 = iso2.upper()
    if len(iso2) != 2 or not iso2.isalpha():
        return ""
    return chr(0x1F1E6 + ord(iso2[0]) - 65) + chr(0x1F1E6 + ord(iso2[1]) - 65)


def country_name(iso2):
    entry = COUNTRIES.get((iso2 or "").upper())
    return entry[0] if entry else f"Unknown ({iso2})"


def continent(iso2):
    entry = COUNTRIES.get((iso2 or "").upper())
    return entry[1] if entry else "Unknown"


def parse_place_code(code):
    """Split a placeCode into (country_iso2, region_name_or_None).

    "US-NY" -> ("US", "New York"); "DE" -> ("DE", None);
    unknown subdivision -> raw region code; falsy -> ("ZZ", None).
    """
    if not code:
        return ("ZZ", None)
    parts = code.split("-", 1)
    country = parts[0].upper()
    if len(parts) == 2:
        return (country, SUBDIVISIONS.get(code.upper(), parts[1]))
    return (country, None)


COUNTRIES = {
    # --- Africa ---
    "AO": ("Angola", "Africa"), "BF": ("Burkina Faso", "Africa"),
    "BI": ("Burundi", "Africa"), "BJ": ("Benin", "Africa"),
    "BW": ("Botswana", "Africa"), "CD": ("Congo (Kinshasa)", "Africa"),
    "CF": ("Central African Republic", "Africa"), "CG": ("Congo (Brazzaville)", "Africa"),
    "CI": ("Cote d'Ivoire", "Africa"), "CM": ("Cameroon", "Africa"),
    "CV": ("Cabo Verde", "Africa"), "DJ": ("Djibouti", "Africa"),
    "DZ": ("Algeria", "Africa"), "EG": ("Egypt", "Africa"),
    "ER": ("Eritrea", "Africa"), "ET": ("Ethiopia", "Africa"),
    "GA": ("Gabon", "Africa"), "GH": ("Ghana", "Africa"),
    "GM": ("Gambia", "Africa"), "GN": ("Guinea", "Africa"),
    "GQ": ("Equatorial Guinea", "Africa"), "GW": ("Guinea-Bissau", "Africa"),
    "KE": ("Kenya", "Africa"), "KM": ("Comoros", "Africa"),
    "LR": ("Liberia", "Africa"), "LS": ("Lesotho", "Africa"),
    "LY": ("Libya", "Africa"), "MA": ("Morocco", "Africa"),
    "MG": ("Madagascar", "Africa"), "ML": ("Mali", "Africa"),
    "MR": ("Mauritania", "Africa"), "MU": ("Mauritius", "Africa"),
    "MW": ("Malawi", "Africa"), "MZ": ("Mozambique", "Africa"),
    "NA": ("Namibia", "Africa"), "NE": ("Niger", "Africa"),
    "NG": ("Nigeria", "Africa"), "RE": ("Reunion", "Africa"),
    "RW": ("Rwanda", "Africa"), "SC": ("Seychelles", "Africa"),
    "SD": ("Sudan", "Africa"), "SH": ("Saint Helena", "Africa"),
    "SL": ("Sierra Leone", "Africa"), "SN": ("Senegal", "Africa"),
    "SO": ("Somalia", "Africa"), "SS": ("South Sudan", "Africa"),
    "ST": ("Sao Tome and Principe", "Africa"), "SZ": ("Eswatini", "Africa"),
    "TD": ("Chad", "Africa"), "TG": ("Togo", "Africa"),
    "TN": ("Tunisia", "Africa"), "TZ": ("Tanzania", "Africa"),
    "UG": ("Uganda", "Africa"), "YT": ("Mayotte", "Africa"),
    "ZA": ("South Africa", "Africa"), "ZM": ("Zambia", "Africa"),
    "ZW": ("Zimbabwe", "Africa"),
    # --- Antarctica ---
    "AQ": ("Antarctica", "Antarctica"),
    # --- Asia ---
    "AE": ("United Arab Emirates", "Asia"), "AF": ("Afghanistan", "Asia"),
    "AM": ("Armenia", "Asia"), "AZ": ("Azerbaijan", "Asia"),
    "BD": ("Bangladesh", "Asia"), "BH": ("Bahrain", "Asia"),
    "BN": ("Brunei Darussalam", "Asia"), "BT": ("Bhutan", "Asia"),
    "CN": ("China", "Asia"), "GE": ("Georgia", "Asia"),
    "HK": ("Hong Kong", "Asia"), "ID": ("Indonesia", "Asia"),
    "IL": ("Israel", "Asia"), "IN": ("India", "Asia"),
    "IQ": ("Iraq", "Asia"), "IR": ("Iran", "Asia"),
    "JO": ("Jordan", "Asia"), "JP": ("Japan", "Asia"),
    "KG": ("Kyrgyzstan", "Asia"), "KH": ("Cambodia", "Asia"),
    "KP": ("North Korea", "Asia"), "KR": ("South Korea", "Asia"),
    "KW": ("Kuwait", "Asia"), "KZ": ("Kazakhstan", "Asia"),
    "LA": ("Laos", "Asia"), "LB": ("Lebanon", "Asia"),
    "LK": ("Sri Lanka", "Asia"), "MM": ("Myanmar", "Asia"),
    "MN": ("Mongolia", "Asia"), "MO": ("Macao", "Asia"),
    "MV": ("Maldives", "Asia"), "MY": ("Malaysia", "Asia"),
    "NP": ("Nepal", "Asia"), "OM": ("Oman", "Asia"),
    "PH": ("Philippines", "Asia"), "PK": ("Pakistan", "Asia"),
    "QA": ("Qatar", "Asia"), "SA": ("Saudi Arabia", "Asia"),
    "SG": ("Singapore", "Asia"), "SY": ("Syria", "Asia"),
    "TH": ("Thailand", "Asia"), "TJ": ("Tajikistan", "Asia"),
    "TL": ("Timor-Leste", "Asia"), "TM": ("Turkmenistan", "Asia"),
    "TR": ("Turkey", "Asia"), "TW": ("Taiwan", "Asia"),
    "UZ": ("Uzbekistan", "Asia"), "VN": ("Vietnam", "Asia"),
    "YE": ("Yemen", "Asia"),
    # --- Europe ---
    "AL": ("Albania", "Europe"), "AT": ("Austria", "Europe"),
    "BA": ("Bosnia and Herzegovina", "Europe"), "BE": ("Belgium", "Europe"),
    "BG": ("Bulgaria", "Europe"), "BY": ("Belarus", "Europe"),
    "CH": ("Switzerland", "Europe"), "CY": ("Cyprus", "Europe"),
    "CZ": ("Czechia", "Europe"), "DE": ("Germany", "Europe"),
    "DK": ("Denmark", "Europe"), "EE": ("Estonia", "Europe"),
    "ES": ("Spain", "Europe"), "FI": ("Finland", "Europe"),
    "FO": ("Faroe Islands", "Europe"), "FR": ("France", "Europe"),
    "GB": ("United Kingdom", "Europe"), "GG": ("Guernsey", "Europe"),
    "GI": ("Gibraltar", "Europe"), "GR": ("Greece", "Europe"),
    "HR": ("Croatia", "Europe"), "HU": ("Hungary", "Europe"),
    "IE": ("Ireland", "Europe"), "IM": ("Isle of Man", "Europe"),
    "IS": ("Iceland", "Europe"), "IT": ("Italy", "Europe"),
    "JE": ("Jersey", "Europe"), "LT": ("Lithuania", "Europe"),
    "LU": ("Luxembourg", "Europe"), "LV": ("Latvia", "Europe"),
    "MC": ("Monaco", "Europe"), "MD": ("Moldova", "Europe"),
    "ME": ("Montenegro", "Europe"), "MK": ("North Macedonia", "Europe"),
    "MT": ("Malta", "Europe"), "NL": ("Netherlands", "Europe"),
    "NO": ("Norway", "Europe"), "PL": ("Poland", "Europe"),
    "PT": ("Portugal", "Europe"), "RO": ("Romania", "Europe"),
    "RS": ("Serbia", "Europe"), "RU": ("Russian Federation", "Europe"),
    "SE": ("Sweden", "Europe"), "SI": ("Slovenia", "Europe"),
    "SK": ("Slovakia", "Europe"), "SM": ("San Marino", "Europe"),
    "UA": ("Ukraine", "Europe"), "XK": ("Kosovo", "Europe"),
    # --- North America ---
    "AG": ("Antigua and Barbuda", "North America"), "AI": ("Anguilla", "North America"),
    "AW": ("Aruba", "North America"), "BB": ("Barbados", "North America"),
    "BL": ("Saint Barthelemy", "North America"), "BM": ("Bermuda", "North America"),
    "BS": ("Bahamas", "North America"), "BZ": ("Belize", "North America"),
    "CA": ("Canada", "North America"), "CR": ("Costa Rica", "North America"),
    "CU": ("Cuba", "North America"), "CW": ("Curacao", "North America"),
    "DM": ("Dominica", "North America"), "DO": ("Dominican Republic", "North America"),
    "GD": ("Grenada", "North America"), "GL": ("Greenland", "North America"),
    "GP": ("Guadeloupe", "North America"), "GT": ("Guatemala", "North America"),
    "HN": ("Honduras", "North America"), "HT": ("Haiti", "North America"),
    "JM": ("Jamaica", "North America"), "KN": ("Saint Kitts and Nevis", "North America"),
    "KY": ("Cayman Islands", "North America"), "LC": ("Saint Lucia", "North America"),
    "MQ": ("Martinique", "North America"), "MS": ("Montserrat", "North America"),
    "MX": ("Mexico", "North America"), "NI": ("Nicaragua", "North America"),
    "PA": ("Panama", "North America"), "PM": ("Saint Pierre and Miquelon", "North America"),
    "PR": ("Puerto Rico", "North America"), "SV": ("El Salvador", "North America"),
    "SX": ("Sint Maarten", "North America"), "TC": ("Turks and Caicos Islands", "North America"),
    "TT": ("Trinidad and Tobago", "North America"),
    "US": ("United States of America", "North America"),
    "VC": ("Saint Vincent and the Grenadines", "North America"),
    "VG": ("British Virgin Islands", "North America"),
    "VI": ("U.S. Virgin Islands", "North America"),
    # --- Oceania ---
    "AS": ("American Samoa", "Oceania"), "AU": ("Australia", "Oceania"),
    "CC": ("Cocos (Keeling) Islands", "Oceania"), "CK": ("Cook Islands", "Oceania"),
    "FJ": ("Fiji", "Oceania"), "FM": ("Micronesia", "Oceania"),
    "GU": ("Guam", "Oceania"), "KI": ("Kiribati", "Oceania"),
    "MH": ("Marshall Islands", "Oceania"), "MP": ("Northern Mariana Islands", "Oceania"),
    "NC": ("New Caledonia", "Oceania"), "NR": ("Nauru", "Oceania"),
    "NZ": ("New Zealand", "Oceania"), "PF": ("French Polynesia", "Oceania"),
    "PG": ("Papua New Guinea", "Oceania"), "PW": ("Palau", "Oceania"),
    "SB": ("Solomon Islands", "Oceania"), "TO": ("Tonga", "Oceania"),
    "TV": ("Tuvalu", "Oceania"), "UM": ("U.S. Minor Outlying Islands", "Oceania"),
    "VU": ("Vanuatu", "Oceania"), "WF": ("Wallis and Futuna", "Oceania"),
    "WS": ("Samoa", "Oceania"),
    # --- South America ---
    "AR": ("Argentina", "South America"), "BO": ("Bolivia", "South America"),
    "BR": ("Brazil", "South America"), "CL": ("Chile", "South America"),
    "CO": ("Colombia", "South America"), "EC": ("Ecuador", "South America"),
    "FK": ("Falkland Islands", "South America"), "GF": ("French Guiana", "South America"),
    "GY": ("Guyana", "South America"), "PE": ("Peru", "South America"),
    "PY": ("Paraguay", "South America"), "SR": ("Suriname", "South America"),
    "UY": ("Uruguay", "South America"), "VE": ("Venezuela", "South America"),
}

SUBDIVISIONS = {
    # United States
    "US-AL": "Alabama", "US-AK": "Alaska", "US-AZ": "Arizona", "US-AR": "Arkansas",
    "US-CA": "California", "US-CO": "Colorado", "US-CT": "Connecticut", "US-DE": "Delaware",
    "US-FL": "Florida", "US-GA": "Georgia", "US-HI": "Hawaii", "US-ID": "Idaho",
    "US-IL": "Illinois", "US-IN": "Indiana", "US-IA": "Iowa", "US-KS": "Kansas",
    "US-KY": "Kentucky", "US-LA": "Louisiana", "US-ME": "Maine", "US-MD": "Maryland",
    "US-MA": "Massachusetts", "US-MI": "Michigan", "US-MN": "Minnesota", "US-MS": "Mississippi",
    "US-MO": "Missouri", "US-MT": "Montana", "US-NE": "Nebraska", "US-NV": "Nevada",
    "US-NH": "New Hampshire", "US-NJ": "New Jersey", "US-NM": "New Mexico", "US-NY": "New York",
    "US-NC": "North Carolina", "US-ND": "North Dakota", "US-OH": "Ohio", "US-OK": "Oklahoma",
    "US-OR": "Oregon", "US-PA": "Pennsylvania", "US-RI": "Rhode Island", "US-SC": "South Carolina",
    "US-SD": "South Dakota", "US-TN": "Tennessee", "US-TX": "Texas", "US-UT": "Utah",
    "US-VT": "Vermont", "US-VA": "Virginia", "US-WA": "Washington", "US-WV": "West Virginia",
    "US-WI": "Wisconsin", "US-WY": "Wyoming", "US-DC": "District of Columbia",
    # Australia
    "AU-ACT": "Australian Capital Territory", "AU-NSW": "New South Wales",
    "AU-NT": "Northern Territory", "AU-QLD": "Queensland", "AU-SA": "South Australia",
    "AU-TAS": "Tasmania", "AU-VIC": "Victoria", "AU-WA": "Western Australia",
    # Canada
    "CA-AB": "Alberta", "CA-BC": "British Columbia", "CA-MB": "Manitoba",
    "CA-NB": "New Brunswick", "CA-NL": "Newfoundland and Labrador", "CA-NS": "Nova Scotia",
    "CA-NT": "Northwest Territories", "CA-NU": "Nunavut", "CA-ON": "Ontario",
    "CA-PE": "Prince Edward Island", "CA-QC": "Quebec", "CA-SK": "Saskatchewan",
    "CA-YT": "Yukon",
    # China
    "CN-AH": "Anhui", "CN-BJ": "Beijing", "CN-CQ": "Chongqing", "CN-FJ": "Fujian",
    "CN-GS": "Gansu", "CN-GD": "Guangdong", "CN-GX": "Guangxi", "CN-GZ": "Guizhou",
    "CN-HA": "Henan", "CN-HB": "Hubei", "CN-HE": "Hebei", "CN-HI": "Hainan",
    "CN-HL": "Heilongjiang", "CN-HN": "Hunan", "CN-JL": "Jilin", "CN-JS": "Jiangsu",
    "CN-JX": "Jiangxi", "CN-LN": "Liaoning", "CN-NM": "Inner Mongolia", "CN-NX": "Ningxia",
    "CN-QH": "Qinghai", "CN-SC": "Sichuan", "CN-SD": "Shandong", "CN-SH": "Shanghai",
    "CN-SN": "Shaanxi", "CN-SX": "Shanxi", "CN-TJ": "Tianjin", "CN-XJ": "Xinjiang",
    "CN-XZ": "Tibet", "CN-YN": "Yunnan", "CN-ZJ": "Zhejiang",
}
