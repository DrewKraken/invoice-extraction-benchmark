"""
The 20 US invoices of the "clean" category (clean-us-*).

Plain data: vendor, customer, number, dates, lines, totals block. The corpus
builder (corpus_v1._from_fixture) turns each one into a DocSpec and lays it
out with the shared layout engine. Every company here is invented; phone
numbers use the reserved 555-01xx range.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Vendor:
    name: str
    street: str
    city_state_zip: str
    phone: Optional[str] = None
    email: Optional[str] = None
    tax_id: Optional[str] = None


@dataclass(frozen=True)
class Customer:
    name: str
    street: str
    city_state_zip: str


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: float
    unit_price: float

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class TaxLine:
    label: str
    amount: float
    rate: Optional[float] = None


@dataclass(frozen=True)
class InvoiceSpec:
    name: str
    description: str
    vendor: Vendor
    customer: Customer
    invoice_number: str
    invoice_date_printed: str
    invoice_date_iso: str
    due_date_printed: Optional[str] = None
    due_date_iso: Optional[str] = None
    po_number: Optional[str] = None
    payment_terms: Optional[str] = None
    line_items: List[LineItem] = field(default_factory=list)
    subtotal: float = 0.0
    discount_label: Optional[str] = None
    discount_amount: float = 0.0
    shipping_label: Optional[str] = None
    shipping_amount: float = 0.0
    fees_label: Optional[str] = None
    fees_amount: float = 0.0
    taxes: List[TaxLine] = field(default_factory=list)
    total_printed: float = 0.0
    service_start_printed: Optional[str] = None
    service_end_printed: Optional[str] = None
    service_start_iso: Optional[str] = None
    service_end_iso: Optional[str] = None
    expected_math_correct: bool = True      # False: the printed total deliberately does not add up
    expected_reconciles: bool = False
    layout_variant: int = 0                 # 0..3: font, header side and table style


# ---------------------------------------------------------------------------
# Vendors and customers (invented)
# ---------------------------------------------------------------------------

ACME = Vendor(
    name="Acme Industrial Supply Co",
    street="4820 Commerce Parkway",
    city_state_zip="Columbus, OH 43215",
    phone="(614) 555-0142",
    email="billing@acmeindustrial.com",
    tax_id="31-1234567",
)
NORTHWIND = Vendor(
    name="Northwind Logistics LLC",
    street="1200 Harbor Boulevard, Suite 400",
    city_state_zip="Seattle, WA 98101",
    phone="(206) 555-0199",
    email="accounts@northwind-logistics.com",
    tax_id="91-2345678",
)
BRIGHTWARE = Vendor(
    name="Brightware Software Inc",
    street="550 Market Street",
    city_state_zip="San Francisco, CA 94104",
    phone="(415) 555-0103",
    email="ar@brightware.io",
    tax_id="94-3456789",
)
FOUNDRY = Vendor(
    name="Foundry Metalworks",
    street="88 Industrial Drive",
    city_state_zip="Pittsburgh, PA 15222",
    phone="(412) 555-0167",
    email="invoices@foundrymetal.com",
    tax_id="25-4567890",
)
GREENLEAF = Vendor(
    name="Greenleaf Office Supply",
    street="2200 Peachtree Road NE",
    city_state_zip="Atlanta, GA 30309",
    phone="(404) 555-0178",
    email="billing@greenleaf-office.com",
    tax_id="58-5678901",
)

CUST_HAYES = Customer(
    name="Hayes & Mitchell LLP",
    street="100 Federal Plaza, Suite 1800",
    city_state_zip="Chicago, IL 60603",
)
CUST_RIVERBEND = Customer(
    name="Riverbend Construction",
    street="750 Industrial Way",
    city_state_zip="Denver, CO 80216",
)
CUST_ORION = Customer(
    name="Orion Medical Group",
    street="3400 Research Park Drive",
    city_state_zip="Austin, TX 78759",
)
CUST_COASTAL = Customer(
    name="Coastal Restaurants Inc",
    street="12 Waterfront Way",
    city_state_zip="Miami, FL 33101",
)

# ---------------------------------------------------------------------------
# The 20 invoices
# ---------------------------------------------------------------------------

SPECS: List[InvoiceSpec] = [

    InvoiceSpec(
        name="us_clean_simple",
        description='Three items, sales tax, no shipping or discount.',
        vendor=ACME,
        customer=CUST_HAYES,
        invoice_number="ACM-100145",
        invoice_date_printed="03/12/2024",
        invoice_date_iso="2024-03-12",
        po_number="PO-55210",
        line_items=[
            LineItem("Industrial grade bolts, 1/2-inch x 2-inch (pack of 100)", 4, 48.50),
            LineItem("Heavy-duty steel washers (pack of 200)", 2, 32.00),
            LineItem("Threadlocker adhesive, blue, 10ml", 6, 14.75),
        ],
        subtotal=346.50,
        taxes=[TaxLine("Sales Tax (7.5%)", 25.99, 0.075)],
        total_printed=372.49,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_with_shipping",
        description="A 'Shipping & Handling' line on the totals block.",
        vendor=NORTHWIND,
        customer=CUST_RIVERBEND,
        invoice_number="NWL-20240318-002",
        invoice_date_printed="03/18/2024",
        invoice_date_iso="2024-03-18",
        po_number="PO-RB-00441",
        line_items=[
            LineItem("Pallet jack, 5500 lb capacity", 2, 489.00),
            LineItem("Stretch wrap rolls, 18-inch x 1500 ft", 12, 24.50),
            LineItem("Warehouse floor tape, yellow, 100 ft", 8, 18.75),
        ],
        subtotal=1422.00,
        shipping_label="Shipping & Handling",
        shipping_amount=85.00,
        taxes=[TaxLine("Sales Tax (6.5%)", 92.43, 0.065)],
        total_printed=1599.43,
        layout_variant=1,
    ),

    InvoiceSpec(
        name="us_with_discount",
        description="A 'Less Discount' line on the totals block.",
        vendor=GREENLEAF,
        customer=CUST_ORION,
        invoice_number="GLO-8842",
        invoice_date_printed="02/27/2024",
        invoice_date_iso="2024-02-27",
        line_items=[
            LineItem("Ergonomic mesh office chair, black", 10, 245.00),
            LineItem("Height-adjustable desk, 60-inch walnut", 4, 619.00),
        ],
        subtotal=4926.00,
        discount_label="Less Discount",
        discount_amount=250.00,
        taxes=[TaxLine("Sales Tax (8%)", 374.08, 0.08)],
        total_printed=5050.08,
        layout_variant=2,
    ),

    InvoiceSpec(
        name="us_shipping_and_discount",
        description='Both a shipping line and a discount line.',
        vendor=FOUNDRY,
        customer=CUST_RIVERBEND,
        invoice_number="FND-2024-03-0091",
        invoice_date_printed="03/05/2024",
        invoice_date_iso="2024-03-05",
        po_number="PO-RB-00392",
        line_items=[
            LineItem("Fabricated steel brackets, custom (lot of 50)", 1, 2850.00),
            LineItem("Powder coat finish, gray", 1, 425.00),
        ],
        subtotal=3275.00,
        discount_label="Loyalty Discount",
        discount_amount=164.00,
        shipping_label="Freight (LTL)",
        shipping_amount=185.00,
        taxes=[TaxLine("PA Sales Tax (6%)", 196.50, 0.06)],
        total_printed=3492.50,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_tax_only",
        description='Professional services invoice: subtotal, tax, total.',
        vendor=BRIGHTWARE,
        customer=CUST_HAYES,
        invoice_number="BW-2024-1142",
        invoice_date_printed="03/31/2024",
        invoice_date_iso="2024-03-31",
        payment_terms="Net 30",
        due_date_printed="04/30/2024",
        due_date_iso="2024-04-30",
        line_items=[
            LineItem("Senior engineering consulting (40 hrs @ $245)", 40, 245.00),
            LineItem("Architecture review and documentation", 1, 2200.00),
        ],
        subtotal=12000.00,
        taxes=[TaxLine("CA Sales Tax (8.625%)", 1035.00, 0.08625)],
        total_printed=13035.00,
        layout_variant=3,
    ),

    InvoiceSpec(
        name="us_freight_alias",
        description="Shipping printed as 'Freight'.",
        vendor=NORTHWIND,
        customer=CUST_RIVERBEND,
        invoice_number="NWL-20240322-008",
        invoice_date_printed="03/22/2024",
        invoice_date_iso="2024-03-22",
        line_items=[
            LineItem("Reinforced shipping pallets, 48x40", 20, 38.50),
        ],
        subtotal=770.00,
        shipping_label="Freight",
        shipping_amount=125.00,
        taxes=[TaxLine("Sales Tax (6.5%)", 50.05, 0.065)],
        total_printed=945.05,
        layout_variant=1,
    ),

    InvoiceSpec(
        name="us_delivery_alias",
        description="Shipping printed as 'Delivery Charge'.",
        vendor=GREENLEAF,
        customer=CUST_ORION,
        invoice_number="GLO-9015",
        invoice_date_printed="03/14/2024",
        invoice_date_iso="2024-03-14",
        line_items=[
            LineItem("Whiteboard, 6ft x 4ft magnetic", 3, 189.00),
            LineItem("Dry-erase marker set (12 colors)", 8, 22.50),
        ],
        subtotal=747.00,
        shipping_label="Delivery Charge",
        shipping_amount=35.00,
        taxes=[TaxLine("Sales Tax (8%)", 59.76, 0.08)],
        total_printed=841.76,
        layout_variant=2,
    ),

    InvoiceSpec(
        name="us_sh_abbrev",
        description="Shipping abbreviated as 'S&H'.",
        vendor=ACME,
        customer=CUST_HAYES,
        invoice_number="ACM-100312",
        invoice_date_printed="04/02/2024",
        invoice_date_iso="2024-04-02",
        line_items=[
            LineItem("Precision measuring calipers, digital", 2, 148.00),
            LineItem("Calibration service, annual", 1, 95.00),
        ],
        subtotal=391.00,
        shipping_label="S&H",
        shipping_amount=18.50,
        taxes=[TaxLine("Sales Tax (7.5%)", 29.33, 0.075)],
        total_printed=438.83,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_handling_alias",
        description="Shipping printed as 'Handling Charge'.",
        vendor=FOUNDRY,
        customer=CUST_COASTAL,
        invoice_number="FND-2024-03-0134",
        invoice_date_printed="03/28/2024",
        invoice_date_iso="2024-03-28",
        line_items=[
            LineItem("Custom signage, powder-coated aluminum", 4, 320.00),
        ],
        subtotal=1280.00,
        shipping_label="Handling Charge",
        shipping_amount=42.00,
        taxes=[TaxLine("PA Sales Tax (6%)", 76.80, 0.06)],
        total_printed=1398.80,
        layout_variant=3,
    ),

    InvoiceSpec(
        name="us_trade_discount",
        description="Discount printed as 'Trade Discount'.",
        vendor=ACME,
        customer=CUST_RIVERBEND,
        invoice_number="ACM-100355",
        invoice_date_printed="04/08/2024",
        invoice_date_iso="2024-04-08",
        line_items=[
            LineItem("Heavy-duty storage bins, 27-gal (case of 4)", 5, 82.00),
            LineItem("Industrial shelving unit, 72-inch", 2, 429.00),
        ],
        subtotal=1268.00,
        discount_label="Trade Discount",
        discount_amount=63.40,
        taxes=[TaxLine("Sales Tax (7.5%)", 90.35, 0.075)],
        total_printed=1294.95,
        layout_variant=1,
    ),

    InvoiceSpec(
        name="us_promo_code",
        description='Discount printed as a promo code line.',
        vendor=GREENLEAF,
        customer=CUST_COASTAL,
        invoice_number="GLO-9178",
        invoice_date_printed="04/15/2024",
        invoice_date_iso="2024-04-15",
        line_items=[
            LineItem("Printer paper, 8.5x11 (case of 10 reams)", 4, 54.00),
            LineItem("Toner cartridge, HP compatible", 3, 118.00),
        ],
        subtotal=570.00,
        discount_label="PROMO-SAVE10",
        discount_amount=57.00,
        taxes=[TaxLine("Sales Tax (8%)", 41.04, 0.08)],
        total_printed=554.04,
        layout_variant=2,
    ),

    InvoiceSpec(
        name="us_service_fee",
        description="A separate 'Service Charge' line (not tax, not shipping).",
        vendor=BRIGHTWARE,
        customer=CUST_HAYES,
        invoice_number="BW-2024-1205",
        invoice_date_printed="04/18/2024",
        invoice_date_iso="2024-04-18",
        payment_terms="Net 15",
        due_date_printed="05/03/2024",
        due_date_iso="2024-05-03",
        line_items=[
            LineItem("Cloud infrastructure subscription, March", 1, 8400.00),
        ],
        subtotal=8400.00,
        fees_label="Service Charge",
        fees_amount=125.00,
        taxes=[TaxLine("CA Sales Tax (8.625%)", 724.50, 0.08625)],
        total_printed=9249.50,
        layout_variant=3,
    ),

    InvoiceSpec(
        name="us_fuel_surcharge",
        description="A 'Fuel Surcharge' fee line (not tax).",
        vendor=NORTHWIND,
        customer=CUST_RIVERBEND,
        invoice_number="NWL-20240410-012",
        invoice_date_printed="04/10/2024",
        invoice_date_iso="2024-04-10",
        line_items=[
            LineItem("Freight transport, Seattle to Denver (48 ft dry van)", 1, 2850.00),
        ],
        subtotal=2850.00,
        shipping_label="Accessorial Freight",
        shipping_amount=175.00,
        fees_label="Fuel Surcharge (12%)",
        fees_amount=342.00,
        taxes=[TaxLine("Sales Tax (6.5%)", 185.25, 0.065)],
        total_printed=3552.25,
        layout_variant=1,
    ),

    InvoiceSpec(
        name="us_many_line_items",
        description='15 line items in one table.',
        vendor=GREENLEAF,
        customer=CUST_HAYES,
        invoice_number="GLO-9301",
        invoice_date_printed="04/22/2024",
        invoice_date_iso="2024-04-22",
        po_number="PO-HM-8824",
        line_items=[
            LineItem("Ballpoint pens, blue (box of 60)", 6, 18.50),
            LineItem("Legal pads, yellow, 8.5x14 (pack of 12)", 8, 24.00),
            LineItem("Manila file folders, letter size (box of 100)", 4, 32.50),
            LineItem("Hanging file folders (box of 25)", 5, 18.75),
            LineItem("Three-ring binders, 2-inch (pack of 6)", 3, 42.00),
            LineItem("Sticky notes, 3x3 (pack of 12 pads)", 10, 14.25),
            LineItem("Stapler, heavy-duty, 25-sheet capacity", 4, 28.50),
            LineItem("Staples, standard (box of 5000)", 6, 6.75),
            LineItem("Paper clips, jumbo (box of 100)", 8, 3.50),
            LineItem("Binder clips, assorted sizes", 4, 12.00),
            LineItem("Scissors, 8-inch titanium-bonded", 6, 15.50),
            LineItem("Tape dispensers with refills", 4, 22.00),
            LineItem("Desk organizer, mesh metal", 3, 34.00),
            LineItem("Label maker, electronic", 2, 89.00),
            LineItem("Printer labels, address (pack of 3000)", 5, 28.50),
        ],
        subtotal=1629.25,
        taxes=[TaxLine("Sales Tax (8%)", 130.34, 0.08)],
        total_printed=1759.59,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_single_service",
        description='One-line services invoice, minimal layout.',
        vendor=BRIGHTWARE,
        customer=CUST_ORION,
        invoice_number="BW-2024-1287",
        invoice_date_printed="04/25/2024",
        invoice_date_iso="2024-04-25",
        payment_terms="Due on Receipt",
        line_items=[
            LineItem("Monthly security monitoring and incident response (April 2024)", 1, 4500.00),
        ],
        subtotal=4500.00,
        taxes=[TaxLine("CA Sales Tax (8.625%)", 388.13, 0.08625)],
        total_printed=4888.13,
        service_start_printed="04/01/2024",
        service_end_printed="04/30/2024",
        service_start_iso="2024-04-01",
        service_end_iso="2024-04-30",
        layout_variant=3,
    ),

    InvoiceSpec(
        name="us_net30_terms",
        description='Net 30 payment terms with a printed due date.',
        vendor=ACME,
        customer=CUST_RIVERBEND,
        invoice_number="ACM-100401",
        invoice_date_printed="04/01/2024",
        invoice_date_iso="2024-04-01",
        payment_terms="Net 30",
        due_date_printed="05/01/2024",
        due_date_iso="2024-05-01",
        po_number="PO-RB-00515",
        line_items=[
            LineItem("Safety equipment bundle — hard hats, vests, gloves", 12, 85.00),
            LineItem("Lockout/tagout kit, industrial", 4, 124.00),
        ],
        subtotal=1516.00,
        taxes=[TaxLine("Sales Tax (7.5%)", 113.70, 0.075)],
        total_printed=1629.70,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_zero_shipping_explicit",
        description="Prints 'Shipping: $0.00' explicitly.",
        vendor=GREENLEAF,
        customer=CUST_COASTAL,
        invoice_number="GLO-9412",
        invoice_date_printed="04/30/2024",
        invoice_date_iso="2024-04-30",
        line_items=[
            LineItem("Digital download — office productivity suite (per seat, annual)", 25, 89.00),
        ],
        subtotal=2225.00,
        shipping_label="Shipping",
        shipping_amount=0.00,
        taxes=[TaxLine("Sales Tax (8%)", 178.00, 0.08)],
        total_printed=2403.00,
        layout_variant=2,
    ),

    InvoiceSpec(
        name="us_credit_applied",
        description="A 'Credit Applied' line reduces the total.",
        vendor=FOUNDRY,
        customer=CUST_RIVERBEND,
        invoice_number="FND-2024-04-0088",
        invoice_date_printed="04/18/2024",
        invoice_date_iso="2024-04-18",
        line_items=[
            LineItem("Fabricated railing sections, 8 ft", 6, 385.00),
            LineItem("Installation hardware kit", 6, 48.00),
        ],
        subtotal=2598.00,
        discount_label="Credit Applied (Account #RB-2024-019)",
        discount_amount=150.00,
        taxes=[TaxLine("PA Sales Tax (6%)", 146.88, 0.06)],
        total_printed=2594.88,
        layout_variant=3,
    ),

    InvoiceSpec(
        name="us_two_tax_lines",
        description='State and county tax on separate lines.',
        vendor=ACME,
        customer=CUST_HAYES,
        invoice_number="ACM-100458",
        invoice_date_printed="05/03/2024",
        invoice_date_iso="2024-05-03",
        line_items=[
            LineItem("Pneumatic impact wrench, 1/2-inch drive", 4, 235.00),
            LineItem("Air compressor oil, 1 gallon", 6, 28.00),
        ],
        subtotal=1108.00,
        taxes=[
            TaxLine("OH State Sales Tax (5.75%)", 63.71, 0.0575),
            TaxLine("Franklin County Tax (1.75%)", 19.39, 0.0175),
        ],
        total_printed=1191.10,
        layout_variant=0,
    ),

    InvoiceSpec(
        name="us_overpaid_invoice",
        description='Printed total is about 23% above subtotal + tax with no charge line explaining it: should be flagged.',
        vendor=FOUNDRY,
        customer=CUST_COASTAL,
        invoice_number="FND-2024-05-0044",
        invoice_date_printed="05/09/2024",
        invoice_date_iso="2024-05-09",
        line_items=[
            LineItem("Custom steel gate, 10ft", 1, 1800.00),
            LineItem("Installation labor (6 hrs)", 6, 95.00),
        ],
        subtotal=2370.00,
        taxes=[TaxLine("PA Sales Tax (6%)", 142.20, 0.06)],
        total_printed=3100.00,
        expected_math_correct=False,
        expected_reconciles=False,
        layout_variant=1,
    ),
]
