# Rails Code Agent - Tool Usage Examples

Based on your system where all tools are available:
✓ rg (ripgrep)
✓ tree-sitter-cli
✓ solargraph
✓ ast-grep
✓ ctags

## Example: Analyzing "SELECT * FROM users WHERE email = ?"

Here's how the Rails agent would use each tool to find related code:

### 1. **ripgrep (rg)** - Fast Text Search
```bash
# Find direct string matches
rg "users" --type ruby
rg "email.*=" --type ruby
rg "User\." --type ruby

# Results: Find controller actions, model methods, views
app/models/user.rb:1:class User < ApplicationRecord
app/controllers/users_controller.rb:15:@user = User.find_by(email: params[:email])
app/views/users/show.html.erb:5:<%= @user.email %>
```

### 2. **tree-sitter-cli** - AST-based Code Parsing
```bash
# Parse Ruby files to understand structure
tree-sitter parse app/models/user.rb

# Extract class definitions, method signatures
# Results: Understanding User model structure, associations, validations
class User < ApplicationRecord
  has_many :posts
  validates :email, presence: true
  def find_by_email(email)
```

### 3. **solargraph** - Symbol Resolution & Definitions
```bash
# Start language server for symbol lookup
solargraph stdio

# LSP requests for:
# - Find all references to User class
# - Get method definitions for User.find_by
# - Resolve associations (has_many :posts)
# Results: Precise symbol locations, method signatures, documentation
```

### 4. **ast-grep** - Structural Pattern Matching
```bash
# Find ActiveRecord query patterns
ast-grep -p 'User.find_by($ARGS)' app/

# Find where email is used in conditions
ast-grep -p 'where(email: $_)' app/

# Results: All ActiveRecord queries involving User and email
app/controllers/sessions_controller.rb:8:User.find_by(email: params[:email])
app/services/auth_service.rb:12:User.where(email: email).first
```

### 5. **ctags** - Symbol Indexing
```bash
# Build symbol index
ctags -R --languages=ruby app/

# Query for symbols
# Results: Jump-to-definition for classes, methods, constants
User  app/models/user.rb  1;"  class
find_by_email  app/models/user.rb  15;"  method
email  app/models/user.rb  8;"  attribute
```

## Multi-tier Search Strategy

When you run: `python3 rails_code_agent.py --analyze "SELECT * FROM users WHERE email = ?"`

The agent combines all tools:

### **Tier 1: Symbol Search** (fastest)
- **ctags**: Find User class definition → `app/models/user.rb:1`
- **solargraph**: Get User class methods and associations

### **Tier 2: Structural Search** (precise)
- **ast-grep**: Find email-related queries → `User.find_by(email: ...)`
- **tree-sitter**: Parse model to find email validations, associations

### **Tier 3: Text Search** (comprehensive)
- **rg**: Find all text mentions → controllers, views, tests, comments

### **Tier 4: Rails Convention Mapping** (intelligent)
- **Table "users" → Model "User" → Controller "UsersController"**
- **Find related routes, views, tests by convention**

## Real Example Output

```
Found 8 results:

1. app/models/user.rb:1 (0.95)
   Model definition for table 'users'
   class User < ApplicationRecord

2. app/controllers/users_controller.rb:15 (0.90)
   Email-based user lookup
   @user = User.find_by(email: params[:email])

3. app/controllers/sessions_controller.rb:8 (0.85)
   Authentication using email
   user = User.where(email: email).first

4. app/views/users/show.html.erb:12 (0.75)
   Email display in view
   <div class="email"><%= @user.email %></div>

5. spec/models/user_spec.rb:45 (0.70)
   Email validation test
   it { should validate_presence_of(:email) }
```

## Performance Benefits

- **Symbol search**: <100ms (ctags, solargraph)
- **Structural search**: <500ms (ast-grep, tree-sitter)
- **Text search**: <200ms (ripgrep)
- **Combined results**: <1 second total

Each tool provides different insights:
- **rg**: Finds everything, including comments and strings
- **ctags**: Precise symbol locations
- **solargraph**: Type information and documentation
- **ast-grep**: Structural code patterns
- **tree-sitter**: Deep AST analysis

The Rails agent intelligently combines all these results and ranks them by relevance to give you the most comprehensive code discovery possible!