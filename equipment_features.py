"""Five source-backed feature groups, separate from ratings and commercial terms.

The legacy profile preserves descriptions from the earlier quotation; it is not
manufacturer verification for every catalog entry. The 500 kVA twin profile is
transcribed from the supplied manufacturer's brochure. See the accompanying
assets/equipment-feature-sources.json for provenance and excluded conflicts.
"""

LEGACY_FEATURES = {
    "title": "Product features & equipment",
    "highlights": (
        "Designed for economical operation and maintenance, with a proven engine for rugged use.",
        "Service interval: 500 operating hours / one year, subject to the selected model's confirmed maintenance schedule.",
        "Wide service network across India, with coordinated sales, service and spares support.",
        "CPCB IV+ emission compliance and remote monitoring are subject to confirmation for the selected model and scope.",
        "Compact footprint to support efficient use of installation space.",
        "Single-window warranty support; warranty duration and any extended 5C cover follow the confirmed commercial terms.",
    ),
    "engine": (
        "Mahindra four-stroke, inline, liquid-cooled engine.",
        "Mechanical engine configuration and fuel-consumption performance to be confirmed for the selected model.",
        "Dry air cleaner with indicator.",
        "Electric starter motor and battery-charging alternator.",
        "Lubricating oil and coolant supplied prefilled.",
        "Starting battery: one 12 V DC battery where applicable; confirm the selected model's starting system.",
        "Nominal engine speed: 1500 rpm, subject to model confirmation. Engine model and rated output are listed in the technical specifications.",
    ),
    "alternator": (
        "Brushless, revolving-field, self-excited design.",
        "H-class insulation.",
        "Compact, lightweight construction with sealed bearings.",
        "IS/IEC 60034-1 conformity, subject to confirmation for the supplied alternator.",
        "Voltage, phase rating, power factor and permitted load imbalance must match the confirmed supplied configuration.",
        "Selected kVA and kW ratings are listed in the technical specifications.",
    ),
    "controller": (
        "SEDEMAC GC111X family controller, where specified, with ARM-based processing, graphic LCD and backlit display.",
        "Operating modes: AMF, manual and remote start/stop for supported single-phase and three-phase systems.",
        "Engine monitoring: oil pressure, coolant temperature, fuel level, battery condition and running hours.",
        "Alternator monitoring: line-to-neutral and line-to-line voltage, current, kW/kVA, frequency and power factor.",
        "Engine protections: low oil pressure, high temperature, overspeed, sensor faults, low fuel and battery-voltage faults.",
        "AC protections: under/over voltage and frequency, overload, load imbalance and sensing faults.",
        "Maintenance alerts based on running hours and service due date.",
        "Communication interfaces: USB, RS485 and CAN; configuration through the front panel.",
    ),
    "enclosure": (
        "Designed to meet applicable MoEF / CPCB requirements; confirm certification for the supplied enclosure and DG set.",
        "Operating range of 10 to 55 degrees C without external cooling is subject to confirmation for the selected model and site conditions.",
        "Fade-resistant, UV-resistant powder-coated finish.",
        "Fire-retardant acoustic insulation using PU foam or rockwool, as specified for the supplied enclosure.",
        "Draw-out fuel tank for maintenance, with external fuel-filling provision outside the canopy.",
        "Compact footprint with easy access to serviceable components.",
        "Common mild-steel base frame with anti-vibration mounting pads.",
        "Emission after-treatment system (ATS), as applicable to the confirmed model.",
        "Model-specific dimensions and fuel-tank capacity are listed in the technical specifications.",
    ),
    "section_notes": {
        "highlights": "Confirm model-specific service intervals, emission certification, monitoring and warranty scope.",
        "engine": "Confirm final engine control type, fuel-consumption data and battery arrangement.",
        "alternator": "Electrical ratings must match the confirmed model and phase selection.",
        "controller": "Confirm the controller model and enabled functions for the supplied system. AMF operating capability does not mean that a separately priced AMF panel is included.",
        "enclosure": "Confirm construction, temperature capability, acoustic performance and compliance for the selected model.",
    },
    "note": (
        "General feature descriptions; final equipment configuration, certification and included scope "
        "must be confirmed for the selected model. Model ratings are listed in the technical specifications."
    ),
}


TWIN_500_FEATURES = {
    "title": "Twin DG features & equipment",
    "highlights": (
        "Twin-engine arrangement supports parallel or single-engine operation to match changing demand.",
        "Intelligent load sharing and selective engine operation support efficient partial-load running.",
        "Dual-unit architecture provides redundancy and operational flexibility during maintenance or component issues.",
        "Designed for fluctuating power requirements, with benefits for non-linear loads and motor starting described in the brochure.",
        "Coordinated monitoring and maintenance support uptime and equipment life.",
        "Remote monitoring through app and web platforms supports generator or fleet oversight.",
    ),
    "engine": (
        "Mahindra H6935G1 electronic engines with TCIC aspiration.",
        "Six cylinders per engine (6 x 2); displacement 9.3 x 2 L.",
        "Engine speed: 1500 rpm. Starting system: 24 V.",
        "Rated engine output: 620 hp, as printed in the brochure.",
        "Lubricating oil capacity: 35 x 2 L. Coolant capacity: 31 x 2 L.",
        "Lubricating oil change interval: 500 operating hours.",
    ),
    "alternator": (
        "CG / LS / Stamford or equivalent.",
        "IP23 enclosure with H-class insulation.",
        "Voltage regulation: +/- 1%.",
        "Maximum unbalanced load across phases: 25%.",
        "415 V, three-phase, 50 Hz; 0.8 lagging power factor.",
        "Prime system output: 500 kVA / 400 kW.",
    ),
    "controller": (
        "Intelligent synchronization and real-time monitoring coordinate the two generating units.",
        "Parallel and single-engine operating modes allow output to follow the load requirement.",
        "Automated failover capabilities support continued operation within the available generating capacity.",
        "Remote monitoring covers running hours, engine health, rpm, error logs and operating parameters through app and web platforms.",
        "Maintenance support includes A-check/B-check notifications, preventive schedules and automated maintenance reminders.",
        "Fuel management tracks filling events, consumption patterns and fuel traceability.",
    ),
    "enclosure": (
        "Twin engines and alternators are arranged on a common base with a central control-panel assembly, as illustrated in the brochure.",
        "The illustrated arrangement includes radiators, air-filter assemblies, batteries and ATS assemblies.",
        "Integrated fuel-tank capacity: 780 L. DEF tanks: 50 + 50 L.",
        "Approximate overall dimensions (L x W x H): 8800 x 1600 x 1975 mm.",
        "Cold-starting system, PMG, RTD, BTD, space heater and external AVR are listed as optional accessories.",
    ),
    "section_notes": {
        "highlights": "Performance and running-cost benefits depend on load profile and operating conditions; no quantified savings or uninterrupted full-load output are guaranteed.",
        "engine": "The brochure prints 620 hp without explicitly identifying it as a per-engine or combined value. Final engine supply details require confirmation.",
        "alternator": "Specifications are from the 500 kVA column of the supplied twin DG brochure.",
        "controller": "Confirm controller model, interfaces, enabled protections and connectivity scope. The illustrated AMF/control arrangement does not establish inclusion of a separately priced AMF panel.",
        "enclosure": "Confirm enclosure finish, acoustic rating, temperature range and certification. Optional accessories are included only when expressly priced in the quotation.",
    },
    "note": (
        "Source: supplied Twin DG Set 500/640 kVA brochure, pages 2-7. These descriptions apply "
        "to the 500 kVA (250 x 2) configuration. Confirm the final supplied configuration before order."
    ),
}
