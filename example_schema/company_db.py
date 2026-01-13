from sqlalchemy import (
    Column, String, DateTime, JSON, Integer, Boolean, Float, Date, ForeignKey,
    UniqueConstraint, Numeric, CheckConstraint, Index, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func, text
import enum

Base = declarative_base()

class ReportingSystem(enum.Enum):
    """Enum for reporting system types. This is used for type safety in Python code.
    The database uses a native PostgreSQL enum type for storage."""
    STANDARD = "STANDARD"
    POWER_BI = "POWER_BI" 
    NONE = "NONE"

"""
CompanyConfigs table stores various configurations for each company.
"""
class CompanyConfigs(Base):
    __tablename__ = 'company_configs'
    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False)  # 'company_profile_config' or 'application_config'
    type = Column(String(50), nullable=False)  # e.g., 'PS', 'Vendor', 'Procurer'
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

"""
CompanyProfile table stores the profile data for each company.
"""
class CompanyProfile(Base):
    __tablename__ = 'company_profiles'
    id = Column(Integer, primary_key=True)
    variable = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)  # e.g., 'profile_template', 'settings', 'styling', 'logo' etc.
    value = Column(JSON, nullable=False)
    form_completed = Column(Boolean, default=False)  # Flag to indicate if the profile form is completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

"""
CompanyRelationshipReference table stores references to relationships in the main database.
Used for fast lookups of relationships relevant to this company.
"""
class CompanyRelationshipReference(Base):
    __tablename__ = 'relationship_references'
    id = Column(Integer, primary_key=True)
    relationship_id = Column(Integer, nullable=False)  # ID of relationship in main DB
    related_company_id = Column(Integer, nullable=False)  # ID of the other company in the relationship
    is_source = Column(Boolean, nullable=False)  # True if this company initiated the relationship
    type = Column(String(50), nullable=False)  # e.g., 'vendor', 'procurer', 'subsidiary'
    status = Column(String(20), nullable=False)  # pending, active, rejected, inactive
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

"""
Legacy company relationship table - kept for backward compatibility.
"""
class CompanyRelationship(Base):
    __tablename__ = 'vendor_procurer_relations'
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False)  # For storing string representation of company ID
    status = Column(String(20), nullable=False, default='active')  # active, inactive, pending
    data = Column(JSON, nullable=True)  # Additional relationship data
    type = Column(String(50), nullable=False)  # e.g., 'vendor', 'procurer', 'subsidiary'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

"""
PurchaseOrder table stores purchase order data for each company.
"""
class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    id = Column(Integer, primary_key=True)
    
    # Purchase order details
    date = Column(Date, nullable=False)
    vendor_name = Column(String(255), nullable=False)
    vendor_number = Column(String(50), nullable=False)
    vendor_id = Column(Integer, nullable=False, default=0)  # ID of the matched vendor company
    contact_number = Column(String(50), nullable=False)
    purchase_order_number = Column(String(50), nullable=False)
    material_number = Column(String(50), nullable=False)
    material_description = Column(String(255), nullable=False)
    order_quantity = Column(Float, nullable=False)
    unit_of_measure = Column(String(50), nullable=False)
    net_price = Column(Float, nullable=False)
    total_spend = Column(Float, nullable=False)
    purchasing_division_cost_center = Column(String(100), nullable=False)
    cost_center_id = Column(String(50), nullable=False)
    region = Column(String(50), nullable=False)
    plant = Column(String(50), nullable=False)
    
    # New columns
    industry = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    business_unit = Column(String(100), nullable=False)
    physical_address_province = Column(String(100), nullable=False)
    bbbee_level = Column(String(20), nullable=False)
    black_youth_ownership_percentage = Column(Float, nullable=False)
    black_ownership_percentage = Column(Float, nullable=False)
    women_ownership_percentage = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    expiry_date = Column(Date, nullable=False)
    company_size = Column(String(50), nullable=False)
    payment_terms = Column(String(100), nullable=False)
    
    # Additional spend analysis columns
    all_spend = Column(Float, nullable=False, default=0.0)
    black_owned_spend = Column(Float, nullable=False, default=0.0)
    black_woman_owned_spend = Column(Float, nullable=False, default=0.0)
    qse_spend = Column(Float, nullable=False, default=0.0)
    eme_spend = Column(Float, nullable=False, default=0.0)
    pp_spend = Column(Float, nullable=False, default=0.0)
    multiplier = Column(Float, nullable=False, default=1.0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """
        Convert the model to a dictionary for API responses
        """
        return {
            "id": self.id,
            "date": str(self.date) if hasattr(self, 'date') else None,
            "vendor_name": self.vendor_name,
            "vendor_number": self.vendor_number,
            "vendor_id": self.vendor_id,
            "contact_number": self.contact_number,
            "purchase_order_number": self.purchase_order_number,
            "material_number": self.material_number,
            "material_description": self.material_description,
            "order_quantity": self.order_quantity,
            "unit_of_measure": self.unit_of_measure,
            "net_price": self.net_price,
            "total_spend": self.total_spend,
            "purchasing_division_cost_center": self.purchasing_division_cost_center,
            "cost_center_id": self.cost_center_id,
            "region": self.region,
            "plant": self.plant,
            # New fields
            "industry": self.industry,
            "status": self.status,
            "business_unit": self.business_unit,
            "physical_address_province": self.physical_address_province,
            "bbbee_level": self.bbbee_level,
            "black_youth_ownership_percentage": self.black_youth_ownership_percentage,
            "black_ownership_percentage": self.black_ownership_percentage,
            "women_ownership_percentage": self.women_ownership_percentage,
            "category": self.category,
            "expiry_date": str(self.expiry_date) if hasattr(self, 'expiry_date') else None,
            "company_size": self.company_size,
            "payment_terms": self.payment_terms,
            # Additional spend analysis columns
            "all_spend": self.all_spend,
            "black_owned_spend": self.black_owned_spend,
            "black_woman_owned_spend": self.black_woman_owned_spend,
            "qse_spend": self.qse_spend,
            "eme_spend": self.eme_spend,
            "pp_spend": self.pp_spend,
            "multiplier": self.multiplier,
            # Metadata
            "created_at": str(self.created_at) if hasattr(self, 'created_at') else None,
            "updated_at": str(self.updated_at) if hasattr(self, 'updated_at') else None
        }
    
class Tags(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    company_id = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)  # e.g., company_name, custom, etc.
    reference_id = Column(Integer, nullable=True)  # Optional reference to another entity (e.g. relationship id)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """
        Convert the model to a dictionary for API responses
        """
        return {
            "id": self.id,
            "name": self.name,
            "company_id": self.company_id,
            "type": self.type,
            "reference_id": self.reference_id,
            "created_at": str(self.created_at) if hasattr(self, 'created_at') else None,
            "updated_at": str(self.updated_at) if hasattr(self, 'updated_at') else None
        }

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    category_number = Column(String(50), nullable=False, unique=True)
    category_description = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship to commodities
    commodities = relationship("Commodity", back_populates="category", cascade="all, delete-orphan")

class Commodity(Base):
    __tablename__ = 'commodities'
    id = Column(Integer, primary_key=True)
    commodity_number = Column(String(50), nullable=False, unique=True)
    commodity_description = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    category = relationship("Category", back_populates="commodities")
    product_services = relationship("ProductService", back_populates="commodity", cascade="all, delete-orphan")

class ProductService(Base):
    __tablename__ = 'product_services'
    id = Column(Integer, primary_key=True)
    product_services_number = Column(String(50), nullable=False, unique=True)
    product_services_description = Column(String(255), nullable=False)
    commodity_id = Column(Integer, ForeignKey('commodities.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    commodity = relationship("Commodity", back_populates="product_services")

class RequisitionType(Base):
    __tablename__ = 'requisition_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    
    # Hierarchical structure
    parent_id = Column(Integer, ForeignKey('requisition_types.id'), nullable=True)
    is_parent = Column(Boolean, nullable=False, default=False, server_default='false')  # True for RFQ/RFP/RFI, False for sub-types
    
    # Budget fields (only for sub-types of RFQ/RFP)
    min_budget = Column(Numeric(15, 2), nullable=True)  # Only for sub-types
    max_budget = Column(Numeric(15, 2), nullable=True)  # Only for sub-types
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "(is_parent = true AND parent_id IS NULL AND min_budget IS NULL AND max_budget IS NULL) OR "
            "(is_parent = false AND parent_id IS NOT NULL AND min_budget IS NOT NULL AND max_budget IS NOT NULL)",
            name='valid_hierarchy_structure'
        ),
        CheckConstraint('min_budget IS NULL OR min_budget >= 0', name='min_budget_non_negative'),
        CheckConstraint('max_budget IS NULL OR max_budget > min_budget', name='max_greater_than_min'),
        Index('idx_requisition_types_parent', 'parent_id'),
        Index('idx_requisition_types_is_parent', 'is_parent'),
    )
    
    # Relationships
    parent = relationship('RequisitionType', remote_side=[id], backref='children')
    
    def to_dict(self):
        """Convert requisition type to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'is_parent': self.is_parent,
            'min_budget': float(self.min_budget) if self.min_budget else None,
            'max_budget': float(self.max_budget) if self.max_budget else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    department_head = Column(Integer, nullable=True)  # User ID from main_db.users
    workflow_id = Column(Integer, nullable=True)  # Default workflow ID from main_db.workflows
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert department to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'department_head': self.department_head,
            'workflow_id': self.workflow_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BudgetRange(Base):
    """
    Budget ranges per RFQ category (RFQ, RFP only - RFI does not require budgets).
    Each organization can have only ONE budget range per category.
    """
    __tablename__ = 'budget_ranges'
    id = Column(Integer, primary_key=True)
    category = Column(String(10), nullable=False)  # RFQ or RFP (RFI excluded)
    min_amount = Column(Numeric(15, 2), nullable=False)
    max_amount = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint("category IN ('RFQ', 'RFP')", name='valid_category'),
        CheckConstraint('min_amount >= 0', name='min_amount_non_negative'),
        CheckConstraint('max_amount > min_amount', name='max_greater_than_min'),
        Index('idx_budget_ranges_category', 'category'),
    )
    
    def to_dict(self):
        """Convert budget range to dictionary."""
        return {
            'id': self.id,
            'category': self.category,
            'min': float(self.min_amount) if self.min_amount else None,
            'max': float(self.max_amount) if self.max_amount else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Requisition(Base):
    __tablename__ = 'requisitions'
    id = Column(Integer, primary_key=True)
    requisition_number = Column(String(10), nullable=False, unique=True)  # Format: REQ00000
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    type_id = Column(Integer, ForeignKey('requisition_types.id'), nullable=False)  # Parent type (RFQ/RFP/RFI)
    sub_type_id = Column(Integer, ForeignKey('requisition_types.id'), nullable=True)  # Sub-type (Travel, Catering, etc.)
    budget = Column(Float, nullable=False)  # Total budget for all items
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    closing_date = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(Integer, nullable=False)  # Admin user ID
    status = Column(String(50), nullable=False, default='draft')  # draft, pending, approved, rejected
    is_draft = Column(Boolean, nullable=False, default=True)  # True for drafts, False for submitted
    is_deleted = Column(Boolean, nullable=False, default=False)  # For soft deletion
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # When the record was soft deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Workflow related fields
    workflow_id = Column(Integer, nullable=True)  # ID of the selected workflow
    workflow_execution_id = Column(Integer, nullable=True)  # ID of the current workflow execution
    
    # Note: Type/sub-type combination validation is handled in the application layer
    # PostgreSQL doesn't support subqueries in CHECK constraints

    # Relationships
    requisition_type = relationship("RequisitionType", foreign_keys=[type_id])
    requisition_sub_type = relationship("RequisitionType", foreign_keys=[sub_type_id])
    department = relationship("Department")
    items = relationship("RequisitionItem", back_populates="requisition", cascade="all, delete-orphan")

class RequisitionItem(Base):
    __tablename__ = 'requisition_items'
    id = Column(Integer, primary_key=True)
    requisition_id = Column(Integer, ForeignKey('requisitions.id', ondelete='CASCADE'), nullable=False)
    product_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    requisition = relationship("Requisition", back_populates="items")

class ReportingSystemPreference(Base):
    __tablename__ = 'reporting_system_preferences'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, unique=True)
    system = Column(String(50), nullable=False, server_default='STANDARD')
    power_bi_url = Column(String(2048), nullable=True)  # URL to the Power BI dashboard
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ReportingSystemAuditLog(Base):
    __tablename__ = 'reporting_system_audit_logs'
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    user_name = Column(String(200), nullable=False)
    previous_system = Column(String(50), nullable=False)
    new_system = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Evaluation(Base):
    """
    Evaluation table stores evaluation entries created from published sourcing entries.
    Each evaluation contains vendor applications that need to be evaluated by a procurement committee.
    """
    __tablename__ = 'evaluations'
    id = Column(Integer, primary_key=True)
    evaluation_number = Column(String(50), nullable=False, unique=True)  # Format: EVL000/SRC000/REQ00000
    sourcing_id = Column(Integer, ForeignKey('sourcing.id'), nullable=False)
    requisition_id = Column(Integer, ForeignKey('requisitions.id'), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, in_progress, completed
    created_by = Column(Integer, nullable=False)  # User ID who created this (same as sourcing creator)
    is_deleted = Column(Boolean, nullable=False, default=False)  # For soft deletion
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # When the record was soft deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Award related fields
    awarded_at = Column(DateTime(timezone=True), nullable=True)  # When the tender was awarded
    awarded_by = Column(Integer, nullable=True)  # User ID who awarded the tender
    delivery_date = Column(DateTime(timezone=True), nullable=True)  # Expected delivery date
    procurement_documents = Column(JSON, nullable=True)  # Array of procurement/audit documents
    approval_documents = Column(JSON, nullable=True)  # Array of approval documents
    
    # Relationships
    sourcing = relationship("Sourcing", backref="evaluations")
    requisition = relationship("Requisition", backref="evaluations")
    vendor_evaluations = relationship("VendorEvaluation", back_populates="evaluation", cascade="all, delete-orphan")
    
    # Ensure only one evaluation per sourcing entry
    __table_args__ = (
        UniqueConstraint('sourcing_id', name='unique_sourcing_evaluation'),
    )

class VendorEvaluation(Base):
    """
    VendorEvaluation table stores evaluation details for each vendor application.
    Each committee member evaluates each vendor based on legislative compliance and technical criteria.
    """
    __tablename__ = 'vendor_evaluations'
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False)
    application_id = Column(Integer, ForeignKey('sourcing_applications.id', ondelete='CASCADE'), nullable=False)
    evaluator_id = Column(Integer, nullable=False)  # User ID of the committee member
    legislative_compliant = Column(Boolean, nullable=True)  # Yes/No for legislative compliance
    technical_score = Column(Float, nullable=True)  # Score given by the evaluator
    comments = Column(String(1000), nullable=True)  # Comments from the evaluator
    status = Column(String(50), nullable=False, default='pending')  # pending, in_progress, completed, awarded
    is_awarded = Column(Boolean, nullable=False, default=False)  # Whether this vendor was awarded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    evaluation = relationship("Evaluation", back_populates="vendor_evaluations")
    application = relationship("SourcingApplication", back_populates="vendor_evaluations")
    
    # Ensure one evaluation per vendor per evaluator
    __table_args__ = (
        UniqueConstraint('evaluation_id', 'application_id', 'evaluator_id', name='unique_vendor_evaluator'),
    )


class Sourcing(Base):
    """
    Sourcing table stores sourcing entries created from approved requisitions.
    ProcurerAdmin can upload documents and submit for approval through workflow system.
    """
    __tablename__ = 'sourcing'
    id = Column(Integer, primary_key=True)
    sourcing_number = Column(String(50), nullable=False, unique=True)  # Format: SRC000/REQ00000
    requisition_id = Column(Integer, ForeignKey('requisitions.id'), nullable=False)
    document_path = Column(String(255), nullable=True)  # Path to uploaded PDF document
    status = Column(String(50), nullable=False, default='pending')  # pending, approved, rejected, published
    
    # Workflow related fields
    workflow_id = Column(Integer, nullable=True)  # ID of the selected workflow
    workflow_execution_id = Column(Integer, nullable=True)  # ID of the current workflow execution
    closing_date = Column(DateTime(timezone=True), nullable=False)  # Inherited from requisition
    
    created_by = Column(Integer, nullable=False)  # User ID who created this (same as requisition creator)
    is_deleted = Column(Boolean, nullable=False, default=False)  # For soft deletion
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # When the record was soft deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    requisition = relationship("Requisition", backref="sourcing_entries")
    applications = relationship("SourcingApplication", back_populates="sourcing", cascade="all, delete-orphan")
    # evaluations relationship is defined in the Evaluation model using backref

class SourcingApplication(Base):
    """
    SourcingApplication table stores vendor applications for sourcing entries.
    Vendors can fill out the sourcing document and submit their applications.
    """
    __tablename__ = 'sourcing_applications'
    id = Column(Integer, primary_key=True)
    sourcing_id = Column(Integer, ForeignKey('sourcing.id', ondelete='CASCADE'), nullable=False)
    vendor_id = Column(Integer, nullable=False)  # ID of the vendor in the main database
    vendor_company_id = Column(Integer, nullable=True)  # Company ID of the vendor for cross-database reference
    application_number = Column(String(50), nullable=False, unique=True)  # Format: APP000/SRC000
    document_path = Column(String(255), nullable=True)  # Path to uploaded filled document
    additional_documents = Column(JSON, nullable=True)  # Array of additional supporting documents
    price = Column(Numeric(precision=15, scale=2), nullable=True)  # Price quote provided by the vendor
    status = Column(String(50), nullable=False, default='submitted')  # Only 'submitted' status is used now
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sourcing = relationship("Sourcing", back_populates="applications")
    vendor_evaluations = relationship("VendorEvaluation", back_populates="application", cascade="all, delete-orphan")
    
    # Ensure vendor can only submit one application per sourcing
    __table_args__ = (
        UniqueConstraint('sourcing_id', 'vendor_id', name='unique_vendor_application'),
    )

# ==============================================================================
# Order Management Models
# ==============================================================================

class Order(PurchaseOrder):
    """
    Order table inherits from PurchaseOrder and adds additional fields for tender-specific data.
    """
    __tablename__ = 'orders'
    __mapper_args__ = {'polymorphic_identity': 'order'}
    
    id = Column(Integer, ForeignKey('purchase_orders.id'), primary_key=True)
    evaluation_id = Column(Integer, ForeignKey('evaluations.id'), nullable=True)
    sourcing_application_id = Column(Integer, ForeignKey('sourcing_applications.id'), nullable=True)
    requisition_id = Column(Integer, ForeignKey('requisitions.id'), nullable=True)
    exempt_order_id = Column(Integer, ForeignKey('exempt_orders.id'), nullable=True)  # Link to exempt orders
    order_type = Column(String(50), nullable=True)  # 'purchase_order', 'framework_order', 'contract', 'exempt_order'
    
    # Value tracking
    total_order_value = Column(Float, nullable=True)  # Set when order type is chosen
    consumed_value = Column(Float, nullable=True, default=0.0)  # For framework orders
    remaining_value = Column(Float, nullable=True)  # For framework orders
    
    # Dates
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    # Documents
    documents = Column(JSON, nullable=True)  # Array of documents

    # Relationships
    evaluation = relationship("Evaluation", backref="orders")
    sourcing_application = relationship("SourcingApplication", backref="orders")
    requisition = relationship("Requisition", backref="orders")
    exempt_order = relationship("ExemptOrder", backref="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    # invoices relationship is defined in Invoice model using backref

class OrderItem(Base):
    """
    OrderItem table stores individual items within an order.
    """
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    item_number = Column(String(50), nullable=True)
    uom = Column(String(50), nullable=True)  # Unit of Matter
    material_number = Column(String(50), nullable=True)
    order_quantity = Column(Float, nullable=True)
    description = Column(String(1000), nullable=True)
    price_per_unit = Column(Float, nullable=True)
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    net_value = Column(Float, nullable=True)  # Calculated: order_quantity * price_per_unit
    gross_value = Column(Float, nullable=True)  # Net value + taxes/additional charges
    
    # Value tracking
    maximum_value = Column(Float, nullable=True)  # For framework orders: total allowed value
    consumed_value = Column(Float, nullable=True, default=0.0)  # For framework orders: sum of releases
    remaining_value = Column(Float, nullable=True)  # For framework orders: maximum_value - consumed_value
    
    # Contract-specific fields
    contract_id = Column(String(100), nullable=True)
    contract_value = Column(Float, nullable=True)  # Total contract value
    payment_schedule = Column(JSON, nullable=True)  # Milestone payments structure
    scope_of_work = Column(String(2000), nullable=True)
    delivery_closing_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    order = relationship("Order", back_populates="items")
    releases = relationship("FrameworkOrderRelease", back_populates="order_item", cascade="all, delete-orphan")

class FrameworkOrderRelease(Base):
    """
    FrameworkOrderRelease table tracks releases for framework order items.
    """
    __tablename__ = 'framework_order_releases'
    id = Column(Integer, primary_key=True)
    order_item_id = Column(Integer, ForeignKey('order_items.id', ondelete='CASCADE'), nullable=False)
    release_quantity = Column(Float, nullable=False)
    release_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    order_item = relationship("OrderItem", back_populates="releases")

# ==============================================================================
# Exempt Order Models
# ==============================================================================

class ExemptOrder(Base):
    """
    ExemptOrder table stores orders that bypass the normal requisition/sourcing/evaluation process.
    These are emergency or special circumstance orders that go directly to invoice management.
    """
    __tablename__ = 'exempt_orders'
    id = Column(Integer, primary_key=True)
    exempt_order_number = Column(String(50), nullable=False, unique=True)  # EXO-2025-001, EXO-2025-002...
    
    # Order details
    order_value = Column(Numeric(precision=15, scale=2), nullable=False)
    exemption_reason = Column(Text, nullable=False)
    order_category = Column(String(100), nullable=False)  # Travel, Hotel, IT Services, etc.
    
    # Status tracking
    status = Column(String(50), nullable=False, default='pending')  # pending, completed
    
    # Multiple vendor awards (JSON array)
    awarded_vendors = Column(JSON, nullable=False)  # [{"vendor_id": 123, "vendor_name": "ABC Corp", "vendor_company_id": 456}, ...]
    
    # Value tracking
    total_invoiced_value = Column(Numeric(precision=15, scale=2), nullable=True, default=0.0)  # Sum of paid invoices
    
    # Timestamps
    created_by = Column(Integer, nullable=False)  # User ID who created
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    invoices = relationship("Invoice", back_populates="exempt_order")

# ==============================================================================
# Invoice Management Models
# ==============================================================================

class Invoice(Base):
    """
    Invoice table stores vendor invoices submitted against orders/contracts or exempt orders.
    """
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=True)
    exempt_order_id = Column(Integer, ForeignKey('exempt_orders.id', ondelete='CASCADE'), nullable=True)
    
    # Invoice details
    company_name = Column(String(255), nullable=True)
    invoice_number = Column(String(100), nullable=False)
    date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    
    # Pricing details
    price_excluding_vat = Column(Numeric(precision=15, scale=2), nullable=True)
    vat = Column(Numeric(precision=15, scale=2), nullable=True)
    price_including_vat = Column(Numeric(precision=15, scale=2), nullable=True)
    value = Column(Numeric(precision=15, scale=2), nullable=False)  # Total value (price including VAT)
    quantity = Column(Float, nullable=True)
    
    status = Column(String(50), nullable=False, default='awaiting-payment')  # awaiting-payment, rejected, paid
    
    # Document details
    document_url = Column(String(500), nullable=True)
    document_name = Column(String(255), nullable=True)
    file_name = Column(String(255), nullable=True)
    
    # Vendor bank details
    account_name = Column(String(255), nullable=True)
    account_number = Column(String(50), nullable=True)
    bank_name = Column(String(255), nullable=True)
    branch_code = Column(String(20), nullable=True)
    account_type = Column(String(50), nullable=True)
    
    # Vendor compliance details
    csd_number = Column(String(50), nullable=True)
    vat_number = Column(String(50), nullable=True)
    
    # Timestamps
    uploaded_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order = relationship("Order", backref="invoices")
    exempt_order = relationship("ExemptOrder", back_populates="invoices")
    delivery_notes = relationship("DeliveryNote", back_populates="invoice", cascade="all, delete-orphan")
    
    # Ensure unique invoice number per order or exempt order
    __table_args__ = (
        UniqueConstraint('order_id', 'invoice_number', name='unique_invoice_per_order'),
    )

class DeliveryNote(Base):
    """
    DeliveryNote table stores delivery notes uploaded by clients to verify invoice deliveries.
    """
    __tablename__ = 'delivery_notes'
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    
    # Document details
    document_url = Column(String(500), nullable=True)
    document_name = Column(String(255), nullable=True)
    file_name = Column(String(255), nullable=True)
    
    # Upload details
    uploaded_by = Column(Integer, nullable=False)  # User ID who uploaded
    uploaded_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Approval/Rejection details
    approval_reason = Column(Text, nullable=True)
    approved_by = Column(Integer, nullable=True)  # User ID who approved
    approved_date = Column(DateTime(timezone=True), nullable=True)
    
    rejection_reason = Column(Text, nullable=True)
    rejected_by = Column(Integer, nullable=True)  # User ID who rejected
    rejected_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    invoice = relationship("Invoice", back_populates="delivery_notes")
