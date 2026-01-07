// Neo4j Data Validation Checks
// Run this file to validate the integrity of your Vault identity graph
//
// Usage: cypher-shell -a bolt://localhost:7687 -u neo4j -p vaultgraph123 < validation_checks.cypher

// ============================================================================
// CHECK 1: Circular Group Dependencies
// ============================================================================
MATCH path = (g:IdentityGroup)-[:HAS_SUBGROUP*]->(g)
WITH collect(path) as circularPaths, count(path) as circularCount
RETURN '✓ Circular Dependencies' as Check,
       CASE WHEN circularCount = 0
            THEN 'PASS: No circular group dependencies found'
            ELSE 'FAIL: Found ' + toString(circularCount) + ' circular dependencies'
       END as Result,
       circularCount as Count;

// ============================================================================
// CHECK 2: Orphaned Identities
// ============================================================================
MATCH (i:Identity)
WHERE NOT (i)-[:MEMBER_OF]->()
WITH collect(i.name) as orphans, count(i) as orphanCount
RETURN '✓ Orphaned Identities' as Check,
       CASE WHEN orphanCount = 0
            THEN 'PASS: All identities belong to at least one group'
            ELSE 'WARNING: Found ' + toString(orphanCount) + ' identities not in any group'
       END as Result,
       orphanCount as Count,
       orphans as OrphanedIdentities;

// ============================================================================
// CHECK 3: Identities Without Authentication
// ============================================================================
MATCH (i:Identity)
WHERE NOT (i)-[:AUTHENTICATES_VIA]->()
WITH collect(i.name) as noAuth, count(i) as noAuthCount
RETURN '✓ Authentication Coverage' as Check,
       CASE WHEN noAuthCount = 0
            THEN 'PASS: All identities have authentication methods'
            ELSE 'FAIL: Found ' + toString(noAuthCount) + ' identities without authentication'
       END as Result,
       noAuthCount as Count,
       noAuth as IdentitiesWithoutAuth;

// ============================================================================
// CHECK 4: Empty Groups
// ============================================================================
MATCH (g:IdentityGroup)
WHERE NOT ()-[:MEMBER_OF]->(g)
AND NOT (g)-[:HAS_SUBGROUP]->()
WITH collect(g.name) as emptyGroups, count(g) as emptyCount
RETURN '✓ Empty Groups' as Check,
       CASE WHEN emptyCount = 0
            THEN 'PASS: No empty groups found'
            ELSE 'WARNING: Found ' + toString(emptyCount) + ' empty groups'
       END as Result,
       emptyCount as Count,
       emptyGroups as EmptyGroups;

// ============================================================================
// CHECK 5: Unused Policies
// ============================================================================
MATCH (p:Policy)
WHERE NOT ()-[:HAS_POLICY]->(p)
WITH collect(p.name) as unusedPolicies, count(p) as unusedCount
RETURN '✓ Policy Usage' as Check,
       CASE WHEN unusedCount = 0
            THEN 'PASS: All policies are assigned'
            ELSE 'WARNING: Found ' + toString(unusedCount) + ' unused policies'
       END as Result,
       unusedCount as Count,
       unusedPolicies as UnusedPolicies;

// ============================================================================
// CHECK 6: SPIFFE ID Format Validation
// ============================================================================
MATCH (i:Identity)
WHERE NOT i.spiffe_id STARTS WITH 'spiffe://vault/'
WITH collect({name: i.name, spiffe_id: i.spiffe_id}) as invalid, count(i) as invalidCount
RETURN '✓ SPIFFE ID Format' as Check,
       CASE WHEN invalidCount = 0
            THEN 'PASS: All SPIFFE IDs have correct format'
            ELSE 'FAIL: Found ' + toString(invalidCount) + ' invalid SPIFFE IDs'
       END as Result,
       invalidCount as Count,
       invalid as InvalidSPIFFEIDs;

// ============================================================================
// CHECK 7: Duplicate Vault IDs
// ============================================================================
MATCH (i:Identity)
WITH i.vault_id as vaultId, collect(i.name) as identities
WHERE size(identities) > 1
WITH collect({vault_id: vaultId, identities: identities}) as duplicates, count(*) as dupCount
RETURN '✓ Vault ID Uniqueness' as Check,
       CASE WHEN dupCount = 0
            THEN 'PASS: All Vault IDs are unique'
            ELSE 'FAIL: Found ' + toString(dupCount) + ' duplicate Vault IDs'
       END as Result,
       dupCount as Count,
       duplicates as Duplicates;

// ============================================================================
// CHECK 8: GitHub Username Duplicates
// ============================================================================
MATCH (h:HumanIdentity)
WHERE h.github_username IS NOT NULL AND h.github_username <> ''
WITH h.github_username as github, collect(h.name) as humans
WHERE size(humans) > 1
WITH collect({github: github, humans: humans}) as duplicates, count(*) as dupCount
RETURN '✓ GitHub Username Uniqueness' as Check,
       CASE WHEN dupCount = 0
            THEN 'PASS: All GitHub usernames are unique'
            ELSE 'WARNING: Found ' + toString(dupCount) + ' duplicate GitHub usernames'
       END as Result,
       dupCount as Count,
       duplicates as Duplicates;

// ============================================================================
// CHECK 9: Verify All Auth Methods Exist
// ============================================================================
MATCH (a:AuthMethod)
WITH collect(a.type) as authTypes
WITH ['github', 'pki', 'aws', 'jwt'] as expectedTypes, authTypes
WITH [t IN expectedTypes WHERE NOT t IN authTypes] as missing
RETURN '✓ Auth Method Coverage' as Check,
       CASE WHEN size(missing) = 0
            THEN 'PASS: All expected auth methods exist'
            ELSE 'WARNING: Missing auth methods: ' + toString(missing)
       END as Result,
       size(missing) as Count,
       missing as MissingAuthMethods;

// ============================================================================
// SUMMARY STATISTICS
// ============================================================================
MATCH (h:HumanIdentity)
WITH count(h) as humanCount
MATCH (a:ApplicationIdentity)
WITH humanCount, count(a) as appCount
MATCH (g:IdentityGroup)
WITH humanCount, appCount, count(g) as groupCount
MATCH (p:Policy)
WITH humanCount, appCount, groupCount, count(p) as policyCount
MATCH (auth:AuthMethod)
WITH humanCount, appCount, groupCount, policyCount, count(auth) as authMethodCount
MATCH ()-[r:MEMBER_OF]->()
WITH humanCount, appCount, groupCount, policyCount, authMethodCount, count(r) as membershipCount
MATCH ()-[r2:HAS_SUBGROUP]->()
WITH humanCount, appCount, groupCount, policyCount, authMethodCount, membershipCount, count(r2) as subgroupCount
MATCH ()-[r3:AUTHENTICATES_VIA]->()
WITH humanCount, appCount, groupCount, policyCount, authMethodCount, membershipCount, subgroupCount, count(r3) as authCount
MATCH ()-[r4:HAS_POLICY]->()
RETURN '📊 Graph Summary' as Check,
       'Total Statistics' as Result,
       {
         Humans: humanCount,
         Applications: appCount,
         Groups: groupCount,
         Policies: policyCount,
         AuthMethods: authMethodCount,
         Memberships: membershipCount,
         Subgroups: subgroupCount,
         AuthRelationships: authCount,
         PolicyAssignments: count(r4)
       } as Statistics;
