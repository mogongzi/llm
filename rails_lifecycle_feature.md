# Rails Lifecycle Analysis Feature

## New Feature Added

The Rails Code Agent now supports **Rails lifecycle analysis** queries to understand what methods, callbacks, validations, and hooks get invoked during Rails operations.

## Usage Examples

```bash
# Analyze what happens before order creation
python3 rails_code_agent.py --analyze "list all methods invoked before order.create" --project-root /path/to/rails/app

# Check what runs before saving a product
python3 rails_code_agent.py --analyze "what methods are called before product.save" --project-root /path/to/rails/app

# Find callbacks after user update
python3 rails_code_agent.py --analyze "callbacks after user.update" --project-root /path/to/rails/app

# Check hooks around cart destroy
python3 rails_code_agent.py --analyze "hooks around cart.destroy" --project-root /path/to/rails/app
```

## What It Analyzes

### 1. **Model Lifecycle Hooks**
- **Rails callbacks**: `before_save`, `after_create`, `around_update`, etc.
- **Validations**: `validates :field, presence: true`
- **Custom validation methods**: `validate :custom_method`

### 2. **Controller Triggers**
- **Controller actions** that call the operation (`@order.save`, `Product.create`)
- **Method calls** that trigger the lifecycle

### 3. **Application-wide Hooks**
- **Concerns**: Shared callback modules
- **Observers**: Application observers (if used)
- **Initializers**: Application-wide configurations
- **Library code**: Custom lifecycle hooks

## Query Patterns Supported

The feature recognizes these natural language patterns:

- `"methods invoked before [model].[operation]"`
- `"callbacks after [model].[operation]"`
- `"hooks around [model].[operation]"`
- `"what happens before [model].[operation]"`
- `"list all [stage] [operation] methods"`

**Supported stages:**
- `before` - Methods called before the operation
- `after` - Methods called after the operation
- `around` - Methods wrapped around the operation

**Supported operations:**
- `create`, `save`, `update`, `destroy`, `validate`, `commit`

## Sample Output

```
Found 5 results:

1. app/models/order.rb:9 (0.95)
   Rails before create callback in Order model
   validates :name, :address, :email, presence: true

2. app/models/order.rb:10 (0.95)
   Rails before create callback in Order model
   validates :pay_type, inclusion: PAYMENT_TYPES

3. app/controllers/orders_controller.rb:35 (0.85)
   Controller action triggering Order.create
   if @order.save
```

## How It Works

1. **Query Parsing**: Extracts model name, operation, and lifecycle stage using regex patterns
2. **Model Analysis**: Searches the model file for relevant callbacks and validations
3. **Controller Search**: Finds controller actions that trigger the operation
4. **Application Search**: Scans concerns, observers, and initializers for related hooks
5. **Result Ranking**: Orders results by relevance (model hooks highest, app hooks lowest)

## Technical Implementation

The feature is implemented through:

- `_analyze_rails_lifecycle_query()` - Main analysis orchestrator
- `_extract_model_from_lifecycle_query()` - Query parsing with regex
- `_find_model_lifecycle_hooks()` - Model file analysis
- `_find_controller_lifecycle_triggers()` - Controller action search
- `_find_application_lifecycle_hooks()` - Application-wide hook discovery

## Benefits

- **Debugging**: Understand why certain code runs during Rails operations
- **Code Discovery**: Find all places that might affect a model operation
- **Performance Analysis**: Identify heavy callbacks that might slow operations
- **Testing**: Ensure all lifecycle hooks are properly tested
- **Documentation**: Generate comprehensive lifecycle documentation

This feature complements the existing SQL analysis by providing insight into the Ruby/Rails layer that sits on top of database operations.