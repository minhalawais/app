from app import db
from app.models import Customer, Invoice, Payment,ISPPayment, Complaint, InventoryItem, User, BankAccount, ServicePlan, Area, Task, Supplier, InventoryAssignment, InventoryTransaction
from sqlalchemy import func, case
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from pytz import UTC
from sqlalchemy.exc import SQLAlchemyError
from pytz import UTC  # Ensures consistent timezone handling
import uuid
from sqlalchemy.dialects.postgresql import UUID

logger = logging.getLogger(__name__)

def get_executive_summary_data(company_id):
    if not company_id:
        return {'error': 'Invalid company_id. Please provide a valid company ID.'}

    try:
        # Fetch data from the database
        customers = Customer.query.filter_by(company_id=company_id).all()
        invoices = Invoice.query.filter_by(company_id=company_id).all()
        complaints = Complaint.query.join(Customer).filter(Customer.company_id == company_id).all()
        service_plans = ServicePlan.query.filter_by(company_id=company_id).all()

        if not customers:
            print(f"No customers found for company_id {company_id}")
        if not invoices:
            print(f"No invoices found for company_id {company_id}")
        if not complaints:
            print(f"No complaints found for company_id {company_id}")
        if not service_plans:
            print(f"No service plans found for company_id {company_id}")

        # Calculate metrics
        total_active_customers = sum(1 for c in customers if c.is_active)
        monthly_recurring_revenue = sum(float(i.total_amount) for i in invoices if i.invoice_type == 'subscription')
        outstanding_payments = sum(float(i.total_amount) for i in invoices if i.status == 'pending')
        active_complaints = sum(1 for c in complaints if c.status in ['open', 'in_progress'])

        # Generate customer growth data (last 6 months)
        today = datetime.now(UTC)
        customer_growth_data = []
        for i in range(5, -1, -1):
            try:
                month_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(tzinfo=UTC)
                month_end = (month_start + timedelta(days=32)).replace(day=1, tzinfo=UTC) - timedelta(days=1)
                customer_count = sum(1 for c in customers if c.created_at.replace(tzinfo=UTC) <= month_end)
                customer_growth_data.append({
                    'month': month_start.strftime('%b'),
                    'customers': customer_count
                })
            except Exception as e:
                print(f"Error generating growth data for month index {i}: {e}")

        # Generate service plan distribution data
        service_plan_data = []
        for plan in service_plans:
            try:
                count = sum(1 for c in customers if c.service_plan_id == plan.id)
                service_plan_data.append({
                    'name': plan.name,
                    'value': count
                })
            except Exception as e:
                print(f"Error processing service plan {plan.name}: {e}")

        return {
            'total_active_customers': total_active_customers,
            'monthly_recurring_revenue': monthly_recurring_revenue,
            'outstanding_payments': outstanding_payments,
            'active_complaints': active_complaints,
            'customer_growth_data': customer_growth_data,
            'service_plan_data': service_plan_data
        }

    except SQLAlchemyError as db_error:
        print(f"Database error occurred: {db_error}")
        return {
            'error': 'A database error occurred while fetching the executive summary data.'
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            'error': 'An unexpected error occurred while fetching the executive summary data.'
        }


def get_customer_analytics_data(company_id):
    try:
        today = datetime.now(UTC)
        last_month = today - timedelta(days=30)

        # Ensure valid company_id
        if not company_id:
            raise ValueError("Invalid company_id provided.")

        # Calculate acquisition and churn rates
        total_customers = Customer.query.filter_by(company_id=company_id).count()

        if total_customers == 0:
            return {
                'acquisition_rate': 0,
                'churn_rate': 0,
                'avg_customer_lifetime_value': 0,
                'customer_satisfaction_score': 0,
                'customer_distribution': [],
                'service_plan_distribution': []
            }

        new_customers = Customer.query.filter(
            Customer.company_id == company_id,
            Customer.created_at >= last_month
        ).count()

        churned_customers = Customer.query.filter(
            Customer.company_id == company_id,
            Customer.is_active == False,
            Customer.updated_at >= last_month
        ).count()

        acquisition_rate = (new_customers / total_customers) * 100
        churn_rate = (churned_customers / total_customers) * 100

        # Calculate average customer lifetime value (CLV)
        avg_clv = db.session.query(func.avg(Invoice.total_amount)).filter(
            Invoice.company_id == company_id
        ).scalar() or 0

        # Placeholder for customer satisfaction score
        avg_satisfaction = 4.7

        # Get customer distribution by area
        customer_distribution = db.session.query(
            Area.name, func.count(Customer.id)
        ).join(Customer).filter(
            Customer.company_id == company_id
        ).group_by(Area.name).all()

        # Get service plan distribution
        service_plan_distribution = db.session.query(
            ServicePlan.name, func.count(Customer.id)
        ).join(Customer).filter(
            Customer.company_id == company_id
        ).group_by(ServicePlan.name).all()

        return {
            'acquisition_rate': round(acquisition_rate, 2),
            'churn_rate': round(churn_rate, 2),
            'avg_customer_lifetime_value': round(float(avg_clv), 2),
            'customer_satisfaction_score': avg_satisfaction,
            'customer_distribution': [
                {'area': area, 'customers': count} for area, count in customer_distribution
            ],
            'service_plan_distribution': [
                {'name': name, 'value': count} for name, count in service_plan_distribution
            ]
        }
    except ValueError as ve:
        print(f"Value error in get_customer_analytics_data: {ve}")
        return {'error': str(ve)}
    except SQLAlchemyError as e:
        print(f"Database error in get_customer_analytics_data: {e}")
        return {'error': 'A database error occurred while fetching customer analytics data.'}
    except Exception as e:
        print(f"Unexpected error in get_customer_analytics_data: {e}")
        return {'error': 'An unexpected error occurred while fetching customer analytics data.'}

def get_financial_analytics_data(company_id):
    try:
        today = datetime.now()
        six_months_ago = today - timedelta(days=180)

        # Ensure valid company_id
        if not company_id:
            raise ValueError("Invalid company_id provided.")

        # Calculate monthly revenue for the last 6 months
        monthly_revenue = db.session.query(
            func.date_trunc('month', Invoice.billing_start_date).label('month'),
            func.sum(Invoice.total_amount).label('revenue')
        ).filter(
            Invoice.company_id == company_id,
            Invoice.billing_start_date >= six_months_ago
        ).group_by('month').order_by('month').all()

        # Calculate revenue by service plan
        revenue_by_plan = db.session.query(
            ServicePlan.name,
            func.sum(Invoice.total_amount).label('revenue')
        ).join(Customer, Customer.id == Invoice.customer_id
        ).join(ServicePlan, ServicePlan.id == Customer.service_plan_id
        ).filter(Invoice.company_id == company_id
        ).group_by(ServicePlan.name).all()

        # Calculate total revenue
        total_revenue = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.company_id == company_id
        ).scalar() or Decimal(0)

        # Calculate average revenue per user
        total_customers = Customer.query.filter_by(company_id=company_id).count()
        avg_revenue_per_user = float(total_revenue) / total_customers if total_customers > 0 else 0

        # Calculate operating expenses (placeholder - adjust based on your data model)
        operating_expenses = float(total_revenue) * 0.6

        # Calculate net profit margin
        net_profit = float(total_revenue) - operating_expenses
        net_profit_margin = (net_profit / float(total_revenue)) * 100 if total_revenue > 0 else 0

        return {
            'monthly_revenue': [
                {'month': month.strftime('%b'), 'revenue': float(revenue)}
                for month, revenue in monthly_revenue
            ],
            'revenue_by_plan': [
                {'plan': name, 'revenue': float(revenue)}
                for name, revenue in revenue_by_plan
            ],
            'total_revenue': float(total_revenue),
            'avg_revenue_per_user': round(avg_revenue_per_user, 2),
            'operating_expenses': round(operating_expenses, 2),
            'net_profit_margin': round(net_profit_margin, 2)
        }
    except ValueError as ve:
        print(f"Value error in get_financial_analytics_data: {ve}")
        return {'error': str(ve)}
    except SQLAlchemyError as e:
        print(f"Database error in get_financial_analytics_data: {e}")
        return {'error': 'A database error occurred while fetching financial analytics data.'}
    except Exception as e:
        print(f"Unexpected error in get_financial_analytics_data: {e}")
        return {'error': 'An unexpected error occurred while fetching financial analytics data.'}


def get_service_support_metrics(company_id):
    try:
        # Get complaints for the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        complaints = Complaint.query.join(Customer).filter(
            Customer.company_id == company_id,
            Complaint.created_at >= thirty_days_ago
        ).all()

        # Complaint Status Distribution
        status_counts = db.session.query(
            Complaint.status, func.count(Complaint.id)
        ).join(Customer).filter(
            Customer.company_id == company_id
        ).group_by(Complaint.status).all()

        status_distribution = {status: count for status, count in status_counts}

        # Average Resolution Time (in hours)
        avg_resolution_time = db.session.query(
            func.avg(Complaint.resolved_at - Complaint.created_at)
        ).join(Customer).filter(
            Customer.company_id == company_id,
            Complaint.status == 'resolved'
        ).scalar()
        avg_resolution_time = round(avg_resolution_time.total_seconds() / 3600, 1) if avg_resolution_time else 0

        # Customer Satisfaction Rate
        satisfaction_rate = db.session.query(
            func.avg(Complaint.satisfaction_rating)
        ).join(Customer).filter(
            Customer.company_id == company_id,
            Complaint.satisfaction_rating.isnot(None)
        ).scalar()
        satisfaction_rate = round(satisfaction_rate * 20, 1) if satisfaction_rate else 0  # Assuming rating is 1-5, converting to percentage

        # First Contact Resolution Rate
        fcr_complaints = sum(1 for c in complaints if c.resolution_attempts == 1 and c.status == 'resolved')
        fcr_rate = round((fcr_complaints / len(complaints)) * 100, 1) if complaints else 0

        # Support Ticket Volume (last 30 days)
        ticket_volume = len(complaints)

        # Remarks Summary (last 5 non-empty remarks)
        remarks_summary = db.session.query(Complaint.remarks).join(Customer).filter(
            Customer.company_id == company_id,
            Complaint.remarks != None,
            Complaint.remarks != ''
        ).order_by(Complaint.created_at.desc()).limit(5).all()
        remarks_summary = [remark[0] for remark in remarks_summary]

        return {
            'status_distribution': status_distribution,
            'average_resolution_time': avg_resolution_time,
            'customer_satisfaction_rate': satisfaction_rate,
            'first_contact_resolution_rate': fcr_rate,
            'support_ticket_volume': ticket_volume,
            'remarks_summary': remarks_summary
        }
    except Exception as e:
        print(f"Error fetching service support metrics: {e}")
        return {'error': 'An error occurred while fetching service support metrics.'}

def get_stock_level_data(company_id):
    try:
        # Query inventory items grouped by item_type instead of name
        stock_levels = db.session.query(
            InventoryItem.item_type,  # Using item_type instead of name
            func.sum(InventoryItem.quantity)
        ).join(Supplier
        ).filter(Supplier.company_id == company_id
        ).group_by(InventoryItem.item_type).all()

        data = [{'name': item_type, 'quantity': int(quantity)} for item_type, quantity in stock_levels]
        return {'stock_levels': data, 'total_items': sum(item['quantity'] for item in data)}
    except Exception as e:
        print(f"Error fetching stock level data: {e}")
        return {'error': 'An error occurred while fetching stock level data.'}
    
def get_inventory_movement_data(company_id):
    try:
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        movements = db.session.query(
            func.date_trunc('month', InventoryTransaction.performed_at).label('month'),
            func.sum(case((InventoryTransaction.transaction_type == 'assignment', 1), else_=0)).label('assignments'),
            func.sum(case((InventoryTransaction.transaction_type == 'return', 1), else_=0)).label('returns')
        ).join(InventoryItem
        ).join(Supplier
        ).filter(Supplier.company_id == company_id,
                 InventoryTransaction.performed_at >= six_months_ago
        ).group_by('month'
        ).order_by('month').all()

        data = [
            {
                'month': month.strftime('%b'),
                'assignments': int(assignments),
                'returns': int(returns)
            } for month, assignments, returns in movements
        ]
        return {
            'movement_data': data,
            'total_assignments': sum(item['assignments'] for item in data),
            'total_returns': sum(item['returns'] for item in data)
        }
    except Exception as e:
        print(f"Error fetching inventory movement data: {e}")
        return {'error': 'An error occurred while fetching inventory movement data.'}

def get_inventory_metrics(company_id):
    try:
        # Calculate total inventory value
        total_value = db.session.query(
            func.sum(InventoryItem.quantity * InventoryItem.unit_price)
        ).join(Supplier
        ).filter(Supplier.company_id == company_id).scalar() or 0

        # Annual assignments
        annual_assignments = db.session.query(
            func.count(InventoryTransaction.id)
        ).join(InventoryItem
        ).join(Supplier
        ).filter(
            Supplier.company_id == company_id,
            InventoryTransaction.transaction_type == 'assignment',
            InventoryTransaction.performed_at >= datetime.utcnow() - timedelta(days=365)
        ).scalar() or 0

        # Average inventory
        average_inventory = db.session.query(
            func.avg(InventoryItem.quantity)
        ).join(Supplier
        ).filter(Supplier.company_id == company_id).scalar() or 1

        # Inventory turnover calculation
        inventory_turnover = annual_assignments / average_inventory if average_inventory > 0 else 0

        # Low stock items
        low_stock_threshold = 10  # Adjustable threshold
        low_stock_items = db.session.query(
            func.count(InventoryItem.id)
        ).join(Supplier
        ).filter(
            Supplier.company_id == company_id,
            InventoryItem.quantity < low_stock_threshold
        ).scalar() or 0

        # Average assignment duration
        avg_assignment_duration = db.session.query(
            func.avg(InventoryAssignment.returned_at - InventoryAssignment.assigned_at)
        ).join(InventoryItem
        ).join(Supplier
        ).filter(
            Supplier.company_id == company_id,
            InventoryAssignment.returned_at.isnot(None)
        ).scalar()

        avg_assignment_duration = (
            round(avg_assignment_duration.days) if avg_assignment_duration else 0
        )

        return {
            'total_inventory_value': round(float(total_value), 2),
            'inventory_turnover_rate': round(inventory_turnover, 2),
            'low_stock_items': int(low_stock_items),
            'avg_assignment_duration': avg_assignment_duration
        }
    except Exception as e:
        print(f"Error fetching inventory metrics: {e}")
        return {'error': 'An error occurred while fetching inventory metrics.'}

def get_inventory_management_data(company_id):
    try:
        return {
            'stock_level_data': get_stock_level_data(company_id),
            'inventory_movement_data': get_inventory_movement_data(company_id),
            'inventory_metrics': get_inventory_metrics(company_id)
        }
    except Exception as e:
        print(f"Error fetching inventory management data: {e}")
        return {'error': 'An error occurred while fetching inventory management data.'}

def get_employee_analytics_data(company_id):
    try:
        # Get performance data
        performance_data = db.session.query(
            User.first_name,
            User.last_name,
            func.count(Task.id).label('tasks_completed'),
            func.avg(Complaint.satisfaction_rating).label('avg_satisfaction')
        ).outerjoin(Task, (
            User.id == Task.assigned_to) &
            (Task.status == 'completed') &
            (Task.company_id == company_id)
        ).outerjoin(Complaint, User.id == Complaint.assigned_to
        ).outerjoin(Customer, Complaint.customer_id == Customer.id
        ).filter(
            User.company_id == company_id,
            Customer.company_id == company_id
        ).group_by(User.id
        ).order_by(func.count(Task.id).desc()
        ).limit(5).all()

        # Get productivity trend data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=180)
        productivity_data = db.session.query(
            func.date_trunc('month', Task.updated_at).label('month'),
            func.count(Task.id).label('tasks_completed')
        ).filter(
            Task.company_id == company_id,
            Task.status == 'completed',
            Task.updated_at.between(start_date, end_date)
        ).group_by('month'
        ).order_by('month').all()

        # Calculate metrics
        total_employees = User.query.filter_by(company_id=company_id).count()
        total_tasks = Task.query.filter_by(company_id=company_id, status='completed').count()
        avg_tasks = total_tasks / total_employees if total_employees > 0 else 0
        avg_satisfaction = db.session.query(
            func.avg(Complaint.satisfaction_rating)
        ).join(Customer).filter(
            Customer.company_id == company_id
        ).scalar() or 0

        top_performer = (
            max(performance_data, key=lambda x: x.tasks_completed) if performance_data else None
        )

        training_completion_rate = 92  # Placeholder value; replace with actual calculation

        return {
            'performanceData': [
                {
                    'employee': f"{p.first_name} {p.last_name}",
                    'tasks': p.tasks_completed,
                    'satisfaction': round(p.avg_satisfaction or 0, 1)
                } for p in performance_data
            ],
            'productivityTrendData': [
                {
                    'month': p.month.strftime('%b'),
                    'productivity': p.tasks_completed
                } for p in productivity_data
            ],
            'metrics': {
                'avgTasksCompleted': round(avg_tasks, 1),
                'avgSatisfactionScore': round(avg_satisfaction, 1),
                'topPerformer': (
                    f"{top_performer.first_name} {top_performer.last_name}"
                    if top_performer else "N/A"
                ),
                'trainingCompletionRate': training_completion_rate
            }
        }
    except Exception as e:
        print(f"Error fetching employee analytics data: {e}")
        return {'error': 'An error occurred while fetching employee analytics data.'}

def get_area_analytics_data(company_id):
    try:
        # Get area performance data
        area_performance = db.session.query(
            Area.name.label('area'),
            func.count(Customer.id).label('customers'),
            func.sum(Invoice.total_amount).label('revenue')
        ).join(Customer, Customer.area_id == Area.id
        ).outerjoin(Invoice, Invoice.customer_id == Customer.id
        ).filter(Area.company_id == company_id
        ).group_by(Area.name).all()

        # Get service plan distribution data
        service_plan_distribution = db.session.query(
            ServicePlan.name,
            func.count(Customer.id).label('value')
        ).join(Customer
        ).filter(ServicePlan.company_id == company_id
        ).group_by(ServicePlan.name).all()

        # Calculate metrics
        total_customers = sum(area.customers or 0 for area in area_performance)
        total_revenue = sum(area.revenue or 0 for area in area_performance)
        best_performing_area = max(area_performance, key=lambda x: x.revenue or 0, default=None)
        avg_revenue_per_customer = total_revenue / total_customers if total_customers > 0 else 0

        return {
            'areaPerformanceData': [
                {
                    'area': area.area,
                    'customers': area.customers or 0,
                    'revenue': float(area.revenue or 0)
                } for area in area_performance
            ],
            'servicePlanDistributionData': [
                {
                    'name': plan.name,
                    'value': plan.value or 0
                } for plan in service_plan_distribution
            ],
            'metrics': {
                'totalCustomers': total_customers,
                'totalRevenue': float(total_revenue),
                'bestPerformingArea': best_performing_area.area if best_performing_area else None,
                'avgRevenuePerCustomer': float(avg_revenue_per_customer)
            }
        }
    except Exception as e:
        print(f"Error fetching area analytics data: {e}")
        return {'error': 'An error occurred while fetching area analytics data.'}

def get_service_plan_analytics_data(company_id):
    try:
        # Get service plan performance data
        service_plan_performance = db.session.query(
            ServicePlan.name.label('plan'),
            func.count(Customer.id).label('subscribers'),
            func.sum(ServicePlan.price).label('revenue')
        ).join(Customer, Customer.service_plan_id == ServicePlan.id
        ).filter(ServicePlan.company_id == company_id
        ).group_by(ServicePlan.name).all()

        # Get plan adoption trend data (last 6 months)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=180)
        plan_adoption_trend = db.session.query(
            func.date_trunc('month', Customer.created_at).label('month'),
            ServicePlan.name,
            func.count(Customer.id).label('subscribers')
        ).join(ServicePlan, Customer.service_plan_id == ServicePlan.id
        ).filter(ServicePlan.company_id == company_id,
                 Customer.created_at.between(start_date, end_date)
        ).group_by('month', ServicePlan.name
        ).order_by('month').all()

        # Process plan adoption trend data
        trend_data = {}
        for month, plan, subscribers in plan_adoption_trend:
            month_str = month.strftime('%b')
            if month_str not in trend_data:
                trend_data[month_str] = {'month': month_str}
            trend_data[month_str][plan] = subscribers or 0

        # Calculate metrics
        total_subscribers = sum(plan.subscribers or 0 for plan in service_plan_performance)
        total_revenue = sum(plan.revenue or 0 for plan in service_plan_performance)
        most_popular_plan = max(service_plan_performance, key=lambda x: x.subscribers or 0, default=None)
        highest_revenue_plan = max(service_plan_performance, key=lambda x: x.revenue or 0, default=None)

        return {
            'servicePlanPerformanceData': [
                {
                    'plan': plan.plan,
                    'subscribers': plan.subscribers or 0,
                    'revenue': float(plan.revenue or 0)
                } for plan in service_plan_performance
            ],
            'planAdoptionTrendData': list(trend_data.values()),
            'metrics': {
                'totalSubscribers': total_subscribers,
                'totalRevenue': float(total_revenue),
                'mostPopularPlan': most_popular_plan.plan if most_popular_plan else None,
                'highestRevenuePlan': highest_revenue_plan.plan if highest_revenue_plan else None
            }
        }
    except Exception as e:
        print(f"Error fetching service plan analytics data: {e}")
        return {'error': 'An error occurred while fetching service plan analytics data.'}

def get_recovery_collections_data(company_id):
    try:
        # Get recovery performance data for the last 6 months
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=180)
        recovery_performance = db.session.query(
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('recovered'),
            func.sum(Invoice.total_amount).label('total_amount')
        ).join(Invoice, Payment.invoice_id == Invoice.id
        ).filter(Payment.company_id == company_id,
                 Payment.payment_date.between(start_date, end_date)
        ).group_by('month'
        ).order_by('month').all()

        # Get outstanding by age data
        current_date = datetime.utcnow().date()
        outstanding_subquery = db.session.query(
            Invoice.id,
            Invoice.total_amount,
            func.coalesce(func.sum(Payment.amount), 0).label('paid_amount'),
            case(
                (Invoice.due_date > current_date, '0-30 days'),
                (Invoice.due_date <= current_date - timedelta(days=30), '31-60 days'),
                (Invoice.due_date <= current_date - timedelta(days=60), '61-90 days'),
                else_='90+ days'
            ).label('age_group')
        ).outerjoin(Payment, Invoice.id == Payment.invoice_id
        ).filter(Invoice.company_id == company_id, Invoice.status != 'paid'
        ).group_by(Invoice.id, Invoice.total_amount, Invoice.due_date
        ).subquery()

        outstanding_by_age = db.session.query(
            outstanding_subquery.c.age_group,
            func.sum(outstanding_subquery.c.total_amount - outstanding_subquery.c.paid_amount).label('outstanding')
        ).group_by(outstanding_subquery.c.age_group).all()

        # Calculate metrics
        total_payments_subquery = db.session.query(
            Payment.invoice_id,
            func.coalesce(func.sum(Payment.amount), 0).label('total_payments')
        ).group_by(Payment.invoice_id).subquery()

        total_outstanding = db.session.query(
            func.sum(Invoice.total_amount - total_payments_subquery.c.total_payments)
        ).outerjoin(total_payments_subquery, Invoice.id == total_payments_subquery.c.invoice_id
        ).filter(Invoice.company_id == company_id, Invoice.status != 'paid').scalar() or 0

        total_recovered = db.session.query(func.sum(Payment.amount)
        ).filter(Payment.company_id == company_id).scalar() or 0

        total_invoiced = total_recovered + total_outstanding
        recovery_rate = (total_recovered / total_invoiced * 100) if total_invoiced > 0 else 0

        avg_collection_time_result = db.session.query(func.avg(Payment.payment_date - Invoice.due_date)
        ).join(Invoice, Payment.invoice_id == Invoice.id
        ).filter(Payment.company_id == company_id).scalar()

        if isinstance(avg_collection_time_result, Decimal):
            avg_collection_time = round(float(avg_collection_time_result))
        elif isinstance(avg_collection_time_result, timedelta):
            avg_collection_time = round(avg_collection_time_result.days)
        else:
            avg_collection_time = 0

        return {
            'recoveryPerformanceData': [
                {
                    'month': month.strftime('%b'),
                    'recovered': float(recovered or 0),
                    'outstanding': float((total_amount or 0) - (recovered or 0))
                } for month, recovered, total_amount in recovery_performance
            ],
            'outstandingByAgeData': [
                {
                    'name': age_group,
                    'value': float(outstanding or 0)
                } for age_group, outstanding in outstanding_by_age
            ],
            'metrics': {
                'totalRecovered': float(total_recovered),
                'totalOutstanding': float(total_outstanding),
                'recoveryRate': float(recovery_rate),
                'avgCollectionTime': avg_collection_time
            }
        }
    except Exception as e:
        print(f"Error fetching recovery and collections data: {str(e)}")
        return {'error': 'An error occurred while fetching recovery and collections data.'}


def get_bank_account_analytics_data(company_id, filters=None):
    try:
        if filters is None:
            filters = {}
        
        # Base query
        query = db.session.query(
            Payment,
            BankAccount,
            Invoice,
            Customer
        ).join(BankAccount, Payment.bank_account_id == BankAccount.id
        ).join(Invoice, Payment.invoice_id == Invoice.id
        ).join(Customer, Invoice.customer_id == Customer.id
        ).filter(Payment.company_id == company_id)
        
        # Apply filters
        if filters.get('start_date'):
            query = query.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            query = query.filter(Payment.payment_date <= filters['end_date'])
        if filters.get('bank_account_id') and filters['bank_account_id'] != 'all':
            query = query.filter(Payment.bank_account_id == uuid.UUID(filters['bank_account_id']))
        if filters.get('payment_method') and filters['payment_method'] != 'all':
            query = query.filter(Payment.payment_method == filters['payment_method'])
        
        payments_data = query.all()
        
        if not payments_data:
            return {
                'total_payments': 0,
                'payment_trends': [],
                'account_performance': [],
                'payment_method_distribution': [],
                'top_customers': [],
                'cash_flow_trends': [],
                'collection_metrics': [],
                'transaction_metrics': []
            }
        
        # Get all bank accounts for the company
        bank_accounts = BankAccount.query.filter_by(company_id=company_id, is_active=True).all()
        
        # 1. Total Payments Received (per bank account, per month, per year)
        monthly_payments = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('total_amount')
        ).join(Payment
        ).filter(Payment.company_id == company_id)
        
        if filters.get('start_date'):
            monthly_payments = monthly_payments.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            monthly_payments = monthly_payments.filter(Payment.payment_date <= filters['end_date'])
        
        monthly_payments = monthly_payments.group_by(
            BankAccount.bank_name, BankAccount.account_number, 'month'
        ).order_by('month').all()
        
        payment_trends = []
        for bank_name, account_number, month, amount in monthly_payments:
            payment_trends.append({
                'bank_account': f"{bank_name} - {account_number}",
                'month': month.strftime('%Y-%m'),
                'amount': float(amount or 0)
            })
        
        # 2. Outstanding Invoices vs Collected Payments
        outstanding_vs_collected = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.sum(case((Invoice.status == 'paid', Invoice.total_amount), else_=0)).label('collected'),
            func.sum(case((Invoice.status != 'paid', Invoice.total_amount), else_=0)).label('outstanding')
        ).join(Payment, BankAccount.id == Payment.bank_account_id, isouter=True
        ).join(Invoice, Payment.invoice_id == Invoice.id, isouter=True
        ).filter(BankAccount.company_id == company_id
        ).group_by(BankAccount.bank_name, BankAccount.account_number).all()
        
        account_performance = []
        for bank_name, account_number, collected, outstanding in outstanding_vs_collected:
            account_performance.append({
                'bank_account': f"{bank_name} - {account_number}",
                'collected': float(collected or 0),
                'outstanding': float(outstanding or 0)
            })
        
        # 3. Top Paying Customers per bank account
        top_customers = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            Customer.first_name,
            Customer.last_name,
            func.sum(Payment.amount).label('total_paid')
        ).join(Payment
        ).join(Invoice
        ).join(Customer
        ).filter(Payment.company_id == company_id)
        
        if filters.get('start_date'):
            top_customers = top_customers.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            top_customers = top_customers.filter(Payment.payment_date <= filters['end_date'])
        
        top_customers = top_customers.group_by(
            BankAccount.bank_name, BankAccount.account_number, Customer.first_name, Customer.last_name
        ).order_by(func.sum(Payment.amount).desc()).limit(10).all()
        
        top_customers_data = []
        for bank_name, account_number, first_name, last_name, total_paid in top_customers:
            top_customers_data.append({
                'bank_account': f"{bank_name} - {account_number}",
                'customer_name': f"{first_name} {last_name}",
                'total_paid': float(total_paid or 0)
            })
        
        # 4. Average Transaction Value (per bank account)
        avg_transaction = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.avg(Payment.amount).label('avg_amount'),
            func.count(Payment.id).label('transaction_count')
        ).join(Payment
        ).filter(Payment.company_id == company_id)
        
        if filters.get('start_date'):
            avg_transaction = avg_transaction.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            avg_transaction = avg_transaction.filter(Payment.payment_date <= filters['end_date'])
        
        avg_transaction = avg_transaction.group_by(
            BankAccount.bank_name, BankAccount.account_number
        ).all()
        
        transaction_metrics = []
        for bank_name, account_number, avg_amount, count in avg_transaction:
            transaction_metrics.append({
                'bank_account': f"{bank_name} - {account_number}",
                'avg_transaction_value': float(avg_amount or 0),
                'transaction_count': count or 0
            })
        
        # 5. Payment Method Distribution
        payment_method_dist = db.session.query(
            Payment.payment_method,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('amount')
        ).filter(Payment.company_id == company_id)
        
        if filters.get('start_date'):
            payment_method_dist = payment_method_dist.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            payment_method_dist = payment_method_dist.filter(Payment.payment_date <= filters['end_date'])
        
        payment_method_dist = payment_method_dist.group_by(Payment.payment_method).all()
        
        payment_method_data = []
        for method, count, amount in payment_method_dist:
            payment_method_data.append({
                'method': method or 'Unknown',
                'count': count or 0,
                'amount': float(amount or 0)
            })
        
        # 6. Cash Flow Trends
        cash_flow_trends = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('amount')
        ).join(Payment
        ).filter(Payment.company_id == company_id)
        
        if filters.get('start_date'):
            cash_flow_trends = cash_flow_trends.filter(Payment.payment_date >= filters['start_date'])
        if filters.get('end_date'):
            cash_flow_trends = cash_flow_trends.filter(Payment.payment_date <= filters['end_date'])
        
        cash_flow_trends = cash_flow_trends.group_by(
            BankAccount.bank_name, BankAccount.account_number, 'month'
        ).order_by('month').all()
        
        cash_flow_data = []
        for bank_name, account_number, month, amount in cash_flow_trends:
            cash_flow_data.append({
                'bank_account': f"{bank_name} - {account_number}",
                'month': month.strftime('%Y-%m'),
                'amount': float(amount or 0)
            })
        
        # 7. Collection Metrics
        total_company_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.company_id == company_id
        ).scalar() or 1  # Avoid division by zero
        
        collection_metrics = []
        for bank_account in bank_accounts:
            account_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bank_account_id == bank_account.id,
                Payment.company_id == company_id
            ).scalar() or 0
            
            collection_ratio = (float(account_revenue) / float(total_company_revenue)) * 100
            
            collection_metrics.append({
                'bank_account': f"{bank_account.bank_name} - {bank_account.account_number}",
                'collection_ratio': round(collection_ratio, 2),
                'total_collected': float(account_revenue)
            })
        
        return {
            'total_payments': len(payments_data) if payments_data else 0,
            'payment_trends': payment_trends if payment_trends else [],
            'account_performance': account_performance if account_performance else [],
            'payment_method_distribution': payment_method_data if payment_method_data else [],
            'top_customers': top_customers_data if top_customers_data else [],
            'cash_flow_trends': cash_flow_data if cash_flow_data else [],
            'collection_metrics': collection_metrics if collection_metrics else [],
            'transaction_metrics': transaction_metrics if transaction_metrics else [],
            'bank_accounts': [
                {
                    'id': str(acc.id),
                    'name': f"{acc.bank_name} - {acc.account_number}"
                }
                for acc in bank_accounts
            ] if bank_accounts else []
        }
        
    except Exception as e:
        print(f"Error fetching bank account analytics data: {str(e)}")
        # Return empty structure on error
        return {
            'total_payments': 0,
            'payment_trends': [],
            'account_performance': [],
            'payment_method_distribution': [],
            'top_customers': [],
            'cash_flow_trends': [],
            'collection_metrics': [],
            'transaction_metrics': [],
            'bank_accounts': [],
            'error': 'An error occurred while fetching bank account analytics data.'
        }

# In get_unified_financial_data function, add initial balance calculations:
def get_unified_financial_data(company_id, filters=None):
    try:
        if filters is None:
            filters = {}

        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        bank_account_id = filters.get('bank_account_id')
        invoice_status = filters.get('invoice_status')
        payment_method = filters.get('payment_method')
        isp_payment_type = filters.get('isp_payment_type')

        kpi_data = get_financial_kpis(company_id, start_date, end_date, bank_account_id, invoice_status, payment_method, isp_payment_type)
        cash_flow_data = get_cash_flow_analysis(company_id, start_date, end_date, bank_account_id, payment_method, isp_payment_type)
        revenue_expense_data = get_revenue_expense_comparison(company_id, start_date, end_date, bank_account_id, invoice_status)
        bank_performance_data = get_bank_account_performance(company_id, start_date, end_date, bank_account_id)
        collections_data = get_collections_analysis(company_id, start_date, end_date, bank_account_id, invoice_status)
        isp_payment_data = get_isp_payment_analysis(company_id, start_date, end_date, bank_account_id, isp_payment_type)

        # NEW: Calculate initial balance summary
        initial_balance_summary = get_initial_balance_summary(company_id, bank_account_id)
        
        # Update KPI data with initial balance
        kpi_data['total_initial_balance'] = initial_balance_summary['total_initial_balance']
        kpi_data['adjusted_cash_flow'] = kpi_data['net_cash_flow'] + initial_balance_summary['total_initial_balance']
        
        # Update cash flow data with initial balance
        cash_flow_data['initial_balance'] = initial_balance_summary['total_initial_balance']
        cash_flow_data['total_adjusted_flow'] = kpi_data['adjusted_cash_flow']
        
        # Add adjusted flow to monthly trends
        for monthly_trend in cash_flow_data['monthly_trends']:
            monthly_trend['adjusted_flow'] = monthly_trend['net_flow'] + initial_balance_summary['total_initial_balance']

        bank_accounts = BankAccount.query.filter_by(company_id=company_id, is_active=True).all()
        bank_accounts_list = [{'id': str(acc.id), 'name': f"{acc.bank_name} - {acc.account_number}"} for acc in bank_accounts]

        return {
            'kpis': kpi_data,
            'cash_flow': cash_flow_data,
            'revenue_expense': revenue_expense_data,
            'bank_performance': bank_performance_data,
            'collections': collections_data,
            'isp_payments': isp_payment_data,
            'filters': filters,
            'bank_accounts': bank_accounts_list,
            'initial_balance_summary': initial_balance_summary  # NEW
        }
    except Exception as e:
        logger.error(f"Error getting unified financial data: {str(e)}")
        return {'error': 'Failed to fetch unified financial data'}

# NEW: Add function to calculate initial balance summary
def get_initial_balance_summary(company_id, bank_account_id=None):
    try:
        query = BankAccount.query.filter_by(
            company_id=company_id,
            is_active=True
        )
        
        if bank_account_id and bank_account_id != 'all':
            query = query.filter(BankAccount.id == uuid.UUID(bank_account_id))
            
        bank_accounts = query.all()
        
        total_initial_balance = sum(float(acc.initial_balance or 0) for acc in bank_accounts)
        accounts_with_balance = sum(1 for acc in bank_accounts if acc.initial_balance and float(acc.initial_balance) > 0)
        average_balance = total_initial_balance / len(bank_accounts) if bank_accounts else 0
        
        return {
            'total_initial_balance': total_initial_balance,
            'accounts_with_balance': accounts_with_balance,
            'average_balance': round(average_balance, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating initial balance summary: {str(e)}")
        return {
            'total_initial_balance': 0,
            'accounts_with_balance': 0,
            'average_balance': 0
        }

def get_financial_kpis(company_id, start_date=None, end_date=None, bank_account_id=None, invoice_status=None, payment_method=None, isp_payment_type=None):
    try:
        revenue_query = db.session.query(func.sum(Invoice.total_amount)).filter(
            Invoice.company_id == company_id,
            Invoice.is_active == True
        )
        if invoice_status and invoice_status != 'all':
            revenue_query = revenue_query.filter(Invoice.status == invoice_status)

        collections_query = db.session.query(func.sum(Payment.amount)).filter(
            Payment.company_id == company_id,
            Payment.is_active == True,
            Payment.status == 'paid'
        )
        if bank_account_id and bank_account_id != 'all':
            collections_query = collections_query.filter(Payment.bank_account_id == uuid.UUID(bank_account_id))
        if payment_method and payment_method != 'all':
            collections_query = collections_query.filter(Payment.payment_method == payment_method)

        isp_payments_query = db.session.query(func.sum(ISPPayment.amount)).filter(
            ISPPayment.company_id == company_id,
            ISPPayment.is_active == True,
            ISPPayment.status == 'completed'
        )
        if bank_account_id and bank_account_id != 'all':
            isp_payments_query = isp_payments_query.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if isp_payment_type and isp_payment_type != 'all':
            isp_payments_query = isp_payments_query.filter(ISPPayment.payment_type == isp_payment_type)

        if start_date:
            revenue_query = revenue_query.filter(Invoice.billing_start_date >= start_date)
            collections_query = collections_query.filter(Payment.payment_date >= start_date)
            isp_payments_query = isp_payments_query.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            revenue_query = revenue_query.filter(Invoice.billing_start_date <= end_date)
            collections_query = collections_query.filter(Payment.payment_date <= end_date)
            isp_payments_query = isp_payments_query.filter(ISPPayment.payment_date <= end_date)

        total_revenue = revenue_query.scalar() or 0
        total_collections = collections_query.scalar() or 0
        total_isp_payments = isp_payments_query.scalar() or 0

        net_cash_flow = float(total_collections) - float(total_isp_payments)
        collection_efficiency = (float(total_collections) / float(total_revenue) * 100) if float(total_revenue) > 0 else 0
        operating_profit = float(total_collections) - float(total_isp_payments)

        return {
            'total_revenue': float(total_revenue),
            'total_collections': float(total_collections),
            'total_isp_payments': float(total_isp_payments),
            'net_cash_flow': net_cash_flow,
            'collection_efficiency': round(collection_efficiency, 2),
            'operating_profit': round(operating_profit, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating financial KPIs: {str(e)}")
        return {}

def get_cash_flow_analysis(company_id, start_date=None, end_date=None, bank_account_id=None, payment_method=None, isp_payment_type=None):
    try:
        cash_flow_query = db.session.query(
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.sum(Payment.amount).label('inflow'),
            func.sum(ISPPayment.amount).label('outflow')
        ).outerjoin(
            ISPPayment,
            (func.date_trunc('month', Payment.payment_date) == func.date_trunc('month', ISPPayment.payment_date)) &
            (Payment.company_id == ISPPayment.company_id)
        ).filter(
            Payment.company_id == company_id,
            Payment.is_active == True,
            Payment.status == 'paid'
        )

        if bank_account_id and bank_account_id != 'all':
            cash_flow_query = cash_flow_query.filter(Payment.bank_account_id == uuid.UUID(bank_account_id))
        if payment_method and payment_method != 'all':
            cash_flow_query = cash_flow_query.filter(Payment.payment_method == payment_method)

        if start_date:
            cash_flow_query = cash_flow_query.filter(Payment.payment_date >= start_date)
        if end_date:
            cash_flow_query = cash_flow_query.filter(Payment.payment_date <= end_date)

        if bank_account_id and bank_account_id != 'all':
            cash_flow_query = cash_flow_query.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if isp_payment_type and isp_payment_type != 'all':
            cash_flow_query = cash_flow_query.filter(ISPPayment.payment_type == isp_payment_type)

        cash_flow_data = cash_flow_query.group_by('month').order_by('month').all()

        inflow_methods = db.session.query(
            Payment.payment_method,
            func.sum(Payment.amount).label('amount')
        ).filter(
            Payment.company_id == company_id,
            Payment.is_active == True,
            Payment.status == 'paid'
        )
        if bank_account_id and bank_account_id != 'all':
            inflow_methods = inflow_methods.filter(Payment.bank_account_id == uuid.UUID(bank_account_id))
        if payment_method and payment_method != 'all':
            inflow_methods = inflow_methods.filter(Payment.payment_method == payment_method)
        if start_date:
            inflow_methods = inflow_methods.filter(Payment.payment_date >= start_date)
        if end_date:
            inflow_methods = inflow_methods.filter(Payment.payment_date <= end_date)
        inflow_methods = inflow_methods.group_by(Payment.payment_method).all()

        outflow_types = db.session.query(
            ISPPayment.payment_type,
            func.sum(ISPPayment.amount).label('amount')
        ).filter(
            ISPPayment.company_id == company_id,
            ISPPayment.is_active == True
        )
        if bank_account_id and bank_account_id != 'all':
            outflow_types = outflow_types.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if isp_payment_type and isp_payment_type != 'all':
            outflow_types = outflow_types.filter(ISPPayment.payment_type == isp_payment_type)
        if start_date:
            outflow_types = outflow_types.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            outflow_types = outflow_types.filter(ISPPayment.payment_date <= end_date)
        outflow_types = outflow_types.group_by(ISPPayment.payment_type).all()

        return {
            'monthly_trends': [
                {
                    'month': month.strftime('%Y-%m'),
                    'inflow': float(inflow or 0),
                    'outflow': float(outflow or 0),
                    'net_flow': float((inflow or 0) - (outflow or 0))
                } for month, inflow, outflow in cash_flow_data
            ],
            'inflow_breakdown': [{'method': m, 'amount': float(a or 0)} for m, a in inflow_methods],
            'outflow_breakdown': [{'type': t, 'amount': float(a or 0)} for t, a in outflow_types]
        }
    except Exception as e:
        logger.error(f"Error calculating cash flow analysis: {str(e)}")
        return {}

def get_revenue_expense_comparison(company_id, start_date=None, end_date=None, bank_account_id=None, invoice_status=None):
    try:
        # Calculate REVENUE separately (from Invoices)
        revenue_query = db.session.query(
            func.date_trunc('month', Invoice.billing_start_date).label('month'),
            func.sum(Invoice.total_amount).label('revenue')
        ).filter(
            Invoice.company_id == company_id,
            Invoice.is_active == True
        )
        
        if invoice_status and invoice_status != 'all':
            revenue_query = revenue_query.filter(Invoice.status == invoice_status)
        if start_date:
            revenue_query = revenue_query.filter(Invoice.billing_start_date >= start_date)
        if end_date:
            revenue_query = revenue_query.filter(Invoice.billing_start_date <= end_date)
            
        revenue_data = revenue_query.group_by('month').order_by('month').all()
        
        # Calculate EXPENSES separately (from ISPPayments)
        expense_query = db.session.query(
            func.date_trunc('month', ISPPayment.payment_date).label('month'),
            func.sum(ISPPayment.amount).label('expenses')
        ).filter(
            ISPPayment.company_id == company_id,
            ISPPayment.is_active == True,
            ISPPayment.status == 'completed'  # Only count completed payments
        )
        
        if bank_account_id and bank_account_id != 'all':
            expense_query = expense_query.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if start_date:
            expense_query = expense_query.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            expense_query = expense_query.filter(ISPPayment.payment_date <= end_date)
            
        expense_data = expense_query.group_by('month').order_by('month').all()
        
        # Debug logging to identify the issue
        logger.info(f"Revenue data points: {len(revenue_data)}")
        logger.info(f"Expense data points: {len(expense_data)}")
        
        # Create dictionaries for easy merging
        revenue_dict = {month.strftime('%Y-%m'): float(revenue or 0) for month, revenue in revenue_data}
        expense_dict = {month.strftime('%Y-%m'): float(expenses or 0) for month, expenses in expense_data}
        
        # Get all unique months from both datasets
        all_months = sorted(set(list(revenue_dict.keys()) + list(expense_dict.keys())))
        
        # Combine the data
        monthly_comparison = []
        total_revenue = 0
        total_expenses = 0
        
        for month in all_months:
            revenue = revenue_dict.get(month, 0)
            expenses = expense_dict.get(month, 0)
            ratio = (expenses / revenue * 100) if revenue > 0 else 0
            
            monthly_comparison.append({
                'month': month,
                'revenue': revenue,
                'expenses': expenses,
                'ratio': ratio
            })
            
            total_revenue += revenue
            total_expenses += expenses
        
        # Calculate average ratio (only for months with revenue)
        months_with_revenue = [item for item in monthly_comparison if item['revenue'] > 0]
        average_ratio = sum(item['ratio'] for item in months_with_revenue) / len(months_with_revenue) if months_with_revenue else 0
        
        # Additional debug info
        logger.info(f"Total revenue: {total_revenue}")
        logger.info(f"Total expenses: {total_expenses}")
        logger.info(f"Average ratio: {average_ratio}")
        
        return {
            'monthly_comparison': monthly_comparison,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'average_ratio': round(average_ratio, 1)
        }
        
    except Exception as e:
        logger.error(f"Error calculating revenue expense comparison: {str(e)}")
        # Return empty structure on error
        return {
            'monthly_comparison': [],
            'total_revenue': 0,
            'total_expenses': 0,
            'average_ratio': 0
        }

def get_bank_account_performance(company_id, start_date=None, end_date=None, bank_account_id=None):
    try:
        # Get collections per bank account
        collections_query = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.sum(Payment.amount).label('collections')
        ).join(Payment, BankAccount.id == Payment.bank_account_id
        ).filter(
            BankAccount.company_id == company_id,
            BankAccount.is_active == True,
            Payment.is_active == True,
            Payment.status == 'paid'
        )
        
        if bank_account_id and bank_account_id != 'all':
            collections_query = collections_query.filter(BankAccount.id == uuid.UUID(bank_account_id))
        if start_date:
            collections_query = collections_query.filter(Payment.payment_date >= start_date)
        if end_date:
            collections_query = collections_query.filter(Payment.payment_date <= end_date)
            
        collections_query = collections_query.group_by(BankAccount.bank_name, BankAccount.account_number)
        collections_data = collections_query.all()
        
        # Get ISP payments per bank account
        isp_payments_query = db.session.query(
            BankAccount.bank_name,
            BankAccount.account_number,
            func.sum(ISPPayment.amount).label('payments')
        ).join(ISPPayment, BankAccount.id == ISPPayment.bank_account_id
        ).filter(
            BankAccount.company_id == company_id,
            BankAccount.is_active == True,
            ISPPayment.is_active == True,
            ISPPayment.status == 'completed'
        )
        
        if bank_account_id and bank_account_id != 'all':
            isp_payments_query = isp_payments_query.filter(BankAccount.id == uuid.UUID(bank_account_id))
        if start_date:
            isp_payments_query = isp_payments_query.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            isp_payments_query = isp_payments_query.filter(ISPPayment.payment_date <= end_date)
            
        isp_payments_query = isp_payments_query.group_by(BankAccount.bank_name, BankAccount.account_number)
        isp_payments_data = isp_payments_query.all()
        
        # Create dictionaries for easy lookup
        collections_dict = {}
        for bank_name, account_number, collections in collections_data:
            key = f"{bank_name}-{account_number}"
            collections_dict[key] = float(collections or 0)
        
        payments_dict = {}
        for bank_name, account_number, payments in isp_payments_data:
            key = f"{bank_name}-{account_number}"
            payments_dict[key] = float(payments or 0)
        
        # Get all bank accounts to ensure we show all, even with zero transactions
        all_bank_accounts = BankAccount.query.filter_by(
            company_id=company_id, 
            is_active=True
        ).all()
        
        performance_data = []
        for account in all_bank_accounts:
            key = f"{account.bank_name}-{account.account_number}"
            collections = collections_dict.get(key, 0)
            payments = payments_dict.get(key, 0)
            net_flow = collections - payments
            initial_balance = float(account.initial_balance or 0)  # NEW
            
            # Calculate utilization rate (collections / (collections + payments))
            total_flow = collections + payments
            utilization_rate = (collections / total_flow * 100) if total_flow > 0 else 0
            
            performance_data.append({
                'bank_name': account.bank_name,
                'account_number': account.account_number,
                'collections': collections,
                'payments': payments,
                'net_flow': net_flow,
                'initial_balance': initial_balance,  # NEW
                'utilization_rate': round(utilization_rate, 2)
            })
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Error calculating bank account performance: {str(e)}")
        return []

def get_collections_analysis(company_id, start_date=None, end_date=None, bank_account_id=None, invoice_status=None):
    try:
        current_date = datetime.utcnow().date()
        aging_query = db.session.query(
            Invoice.id,
            Invoice.total_amount,
            Invoice.due_date,
            func.coalesce(func.sum(Payment.amount), 0).label('paid_amount')
        ).outerjoin(Payment, Invoice.id == Payment.invoice_id
        ).filter(
            Invoice.company_id == company_id,
            Invoice.is_active == True,
            Invoice.status != 'paid'
        )
        if invoice_status and invoice_status != 'all':
            aging_query = aging_query.filter(Invoice.status == invoice_status)
        if start_date:
            aging_query = aging_query.filter(Invoice.billing_start_date >= start_date)
        if end_date:
            aging_query = aging_query.filter(Invoice.billing_start_date <= end_date)
        if bank_account_id and bank_account_id != 'all':
            aging_query = aging_query.filter((Payment.bank_account_id == uuid.UUID(bank_account_id)) | (Payment.bank_account_id.is_(None)))
        aging_query = aging_query.group_by(Invoice.id, Invoice.total_amount, Invoice.due_date)
        aging_data = aging_query.all()

        aging_buckets = {
            '0-30': 0,
            '31-60': 0,
            '61-90': 0,
            '90+': 0
        }
        
        for invoice_id, total_amount, due_date, paid_amount in aging_data:
            if due_date:
                days_overdue = (current_date - due_date).days
                outstanding = float(total_amount) - float(paid_amount)
                
                if days_overdue <= 30:
                    aging_buckets['0-30'] += outstanding
                elif days_overdue <= 60:
                    aging_buckets['31-60'] += outstanding
                elif days_overdue <= 90:
                    aging_buckets['61-90'] += outstanding
                else:
                    aging_buckets['90+'] += outstanding
        collection_trends = db.session.query(
            func.date_trunc('month', Payment.payment_date).label('month'),
            func.count(Payment.id).label('payment_count'),
            func.sum(Payment.amount).label('collection_amount')
        ).filter(
            Payment.company_id == company_id,
            Payment.is_active == True,
            Payment.status == 'paid'
        )
        if bank_account_id and bank_account_id != 'all':
            collection_trends = collection_trends.filter(Payment.bank_account_id == uuid.UUID(bank_account_id))
        if start_date:
            collection_trends = collection_trends.filter(Payment.payment_date >= start_date)
        if end_date:
            collection_trends = collection_trends.filter(Payment.payment_date <= end_date)
        collection_trends = collection_trends.group_by('month').order_by('month').all()
        
        return {
            'aging_analysis': [
                {'bucket': bucket, 'amount': amount}
                for bucket, amount in aging_buckets.items()
            ],
            'collection_trends': [
                {
                    'month': month.strftime('%Y-%m'),
                    'payment_count': count or 0,
                    'collection_amount': float(amount or 0)
                }
                for month, count, amount in collection_trends
            ],
            'total_outstanding': sum(aging_buckets.values())
        }
        
    except Exception as e:
        logger.error(f"Error calculating collections analysis: {str(e)}")
        return {}

def get_isp_payment_analysis(company_id, start_date=None, end_date=None, bank_account_id=None, isp_payment_type=None):
    try:
        payment_types = db.session.query(
            ISPPayment.payment_type,
            func.sum(ISPPayment.amount).label('total_amount'),
            func.avg(ISPPayment.amount).label('avg_amount'),
            func.count(ISPPayment.id).label('payment_count')
        ).filter(
            ISPPayment.company_id == company_id,
            ISPPayment.is_active == True
        )
        if bank_account_id and bank_account_id != 'all':
            payment_types = payment_types.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if isp_payment_type and isp_payment_type != 'all':
            payment_types = payment_types.filter(ISPPayment.payment_type == isp_payment_type)
        if start_date:
            payment_types = payment_types.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            payment_types = payment_types.filter(ISPPayment.payment_date <= end_date)
        payment_types = payment_types.group_by(ISPPayment.payment_type).all()

        bandwidth_costs = db.session.query(
            func.date_trunc('month', ISPPayment.payment_date).label('month'),
            func.sum(ISPPayment.amount).label('total_cost'),
            func.sum(ISPPayment.bandwidth_usage_gb).label('total_usage')
        ).filter(
            ISPPayment.company_id == company_id,
            ISPPayment.is_active == True,
            ISPPayment.payment_type == 'bandwidth_usage'
        )
        if bank_account_id and bank_account_id != 'all':
            bandwidth_costs = bandwidth_costs.filter(ISPPayment.bank_account_id == uuid.UUID(bank_account_id))
        if start_date:
            bandwidth_costs = bandwidth_costs.filter(ISPPayment.payment_date >= start_date)
        if end_date:
            bandwidth_costs = bandwidth_costs.filter(ISPPayment.payment_date <= end_date)
        bandwidth_costs = bandwidth_costs.group_by('month').order_by('month').all()
        
        # Calculate cost per GB
        bandwidth_analysis = []
        for month, total_cost, total_usage in bandwidth_costs:
            cost_per_gb = float(total_cost or 0) / float(total_usage or 1) if total_usage and total_usage > 0 else 0
            bandwidth_analysis.append({
                'month': month.strftime('%Y-%m'),
                'total_cost': float(total_cost or 0),
                'total_usage': float(total_usage or 0),
                'cost_per_gb': round(cost_per_gb, 4)
            })
        
        return {
            'payment_types': [
                {
                    'type': payment_type,
                    'total_amount': float(total_amount or 0),
                    'avg_amount': float(avg_amount or 0),
                    'payment_count': payment_count or 0
                }
                for payment_type, total_amount, avg_amount, payment_count in payment_types
            ],
            'bandwidth_analysis': bandwidth_analysis,
            'total_isp_payments': sum(float(total_amount or 0) for _, total_amount, _, _ in payment_types)
        }
        
    except Exception as e:
        logger.error(f"Error calculating ISP payment analysis: {str(e)}")
        return {}