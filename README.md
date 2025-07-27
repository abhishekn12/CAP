The CAP Theorem (also known as Brewer’s Theorem) states that in any distributed system, you can only guarantee 2 out of the following 3 properties at a time:

🔁 CAP Trade-offs
✅ CP (Consistency + Partition Tolerance)
    System gives correct data, but may reject requests during partition.
    
    ✅ Strong correctness
    
    ❌ Might be unavailable
    
    📌 Example: MongoDB (with default settings before v5.0)
    
    Prioritizes consistency. During a network split, a minority replica set can't accept writes.
    
    Clients may experience errors rather than reading stale data.

✅ AP (Availability + Partition Tolerance)
System remains available, but data may be stale/inconsistent across replicas.

    ✅ Always responsive
    
    ❌ Data reconciliation later
    
    📌 Example: Cassandra
    
    Prioritizes availability. Allows writes even if some replicas are unreachable.
    
    Uses eventual consistency (gossip protocols, hinted handoffs, etc.)

✅ CA (Consistency + Availability)
Works only in absence of partitions.

    ✅ Always available and consistent — as long as no failure or partition.
    
    ❌ Cannot survive network partitions
    
    📌 Example: PostgreSQL (single-node or replicated without partition tolerance)
    
    Classic RDBMS: transactions (ACID), always consistent.
    
    If partitioned (like in a cluster), availability is impacted or inconsistency occurs.
