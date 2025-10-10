// Neo4j schema for heterogeneous wallet/token/influencer graph
CREATE CONSTRAINT wallet_pk IF NOT EXISTS
FOR (w:Wallet)
REQUIRE w.address IS UNIQUE;

CREATE CONSTRAINT token_pk IF NOT EXISTS
FOR (t:Token)
REQUIRE t.address IS UNIQUE;

CREATE CONSTRAINT influencer_pk IF NOT EXISTS
FOR (i:Influencer)
REQUIRE i.handle IS UNIQUE;

// Relationship indexes for faster traversals
CREATE INDEX transfer_edge IF NOT EXISTS
FOR ()-[r:TRANSFER]-()
ON (r.tx_hash);

CREATE INDEX mention_edge IF NOT EXISTS
FOR ()-[r:MENTIONED]-()
ON (r.message_id);
