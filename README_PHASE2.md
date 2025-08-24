# ARGO Phase 2: Core Agent System

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp .env.template .env

# Edit .env and add your credentials:
# - REDIS_HOST (required)
# - OPENAI_API_KEY (optional)
# - ANTHROPIC_API_KEY (optional)
# - GEMINI_API_KEY (optional)
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Redis Setup

**Option A: Local Redis**
```bash
# Install Redis locally
docker run -d -p 6379:6379 redis:alpine
```

**Option B: Cloud Redis**
```bash
# Add your cloud Redis URL to .env
REDIS_HOST=your-redis-instance.redis.cache.windows.net
REDIS_PASSWORD=your-password
```

### 4. Run the System

```bash
# Start the Strategic Orchestrator
python run_orchestrator.py
```

## 📁 Project Structure

```
c:/argo-813/
├── src/
│   ├── agents/
│   │   ├── base_agent.py              # Base agent framework
│   │   └── orchestrator/
│   │       └── strategic_orchestrator.py  # Master coordinator
│   ├── shared/
│   │   ├── context/
│   │   │   └── shared_context_fabric.py  # Triple memory system
│   │   └── messaging/
│   │       └── agent_protocol.py      # Message protocol v2.0
│   └── infrastructure/
│       └── locks/
│           └── distributed_lock.py    # Resource locking
├── config/
│   └── config.yaml                    # System configuration
├── .env.template                      # Environment template
├── requirements.txt                   # Python dependencies
└── run_orchestrator.py               # Main entry point
```

## 🧠 Core Components

### 1. **Distributed Lock Manager**
- Prevents resource conflicts during parallel execution
- Automatic deadlock detection
- TTL-based lock expiration

### 2. **Shared Context Fabric**
- **Episodic Memory**: Short-term session context (48hr TTL)
- **Semantic Memory**: Permanent knowledge storage
- **Procedural Memory**: Learned patterns and optimizations

### 3. **Agent Message Protocol v2.0**
- Priority-based message routing
- Support for proposals, consensus, and escalations
- Automatic message batching and retry

### 4. **Strategic Orchestrator**
- Goal interpretation from natural language
- Multi-step execution planning
- Automatic agent selection and task distribution
- Conflict resolution and Director approval requests

## 🔧 Configuration

### Redis Configuration
```yaml
redis:
  host: ${REDIS_HOST}
  port: 6379
  password: ${REDIS_PASSWORD}
```

### Agent Configuration
```yaml
agents:
  orchestrator:
    max_concurrent_tasks: 10
    timeout_seconds: 300
```

### Context Configuration
```yaml
context:
  episodic_memory:
    ttl_hours: 48
    max_size_mb: 100
  procedural_memory:
    learning_rate: 0.1
    pattern_threshold: 3
```

## 🎯 Usage Examples

### Basic Task Execution
```python
# The orchestrator will automatically:
# 1. Interpret your intent
# 2. Create an execution plan
# 3. Distribute tasks to agents
# 4. Monitor progress

# Example: "Optimize this application by 40%"
# Results in:
# - Performance analysis
# - Bottleneck identification
# - Solution generation
# - Implementation
# - Validation
```

### Director Approval Flow
```python
# Tasks requiring approval:
# - Budget > $100
# - Production deployment
# - Data deletion/migration
# - External service integration

# The system will:
# 1. Detect approval requirement
# 2. Send proposal to Director
# 3. Wait for approval
# 4. Execute upon approval
```

## 🔍 Monitoring

### Check System Status
```bash
# View logs
tail -f logs/orchestrator.log

# Redis monitoring
redis-cli
> KEYS agent:*
> KEYS lock:*
```

### Statistics
The system logs statistics every 30 seconds:
- Active agents
- Message counts
- Task completion rates
- Lock statistics

## 🚨 Troubleshooting

### Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping

# Check environment variables
echo $REDIS_HOST
```

### Lock Conflicts
```python
# The system automatically handles:
# - Lock timeouts (30s default)
# - Deadlock detection (5s intervals)
# - Automatic retry with backoff
```

### Memory Issues
```yaml
# Adjust in config.yaml:
context:
  episodic_memory:
    max_size_mb: 50  # Reduce if needed
```

## 📊 Performance Metrics

### Expected Performance
- Message processing: <100ms
- Lock acquisition: <50ms
- Context retrieval: <200ms
- Task distribution: <500ms

### Scalability
- Supports 10+ concurrent agents
- Handles 1000+ messages/minute
- Manages 100+ locks simultaneously

## 🔐 Security Notes

1. **Never commit .env file**
2. **Use environment-specific Redis instances**
3. **Rotate API keys regularly**
4. **Monitor for unusual activity patterns**

## 📝 Next Steps

### Phase 3: Creative & Analytical Unit
- [ ] Implement specialized agents
- [ ] Add vector search capabilities
- [ ] Integrate with external APIs

### Phase 4: Autonomous Development
- [ ] Code generation capabilities
- [ ] Automated testing
- [ ] Deployment automation

## 🤝 Director Interface

When the system needs your input:

1. **Approval Requests**: Plans exceeding thresholds
2. **Conflict Resolution**: When agents can't agree
3. **Manual Intervention**: For errors requiring human input

The system will clearly indicate what action is needed and provide options.

## 📞 Support

For issues or questions:
1. Check logs in `logs/orchestrator.log`
2. Review configuration in `config/config.yaml`
3. Verify environment variables in `.env`

---

**Ready to start?** Run `python run_orchestrator.py` and the system will guide you!