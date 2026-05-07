+your_turn(ID, Text, "", Votes, Relation, RelationAbs) : true <-
    Topics = [];
    Variables = [public(relation_abs(RelationAbs), relation(Relation), votes(Votes))];
    ia.saveLogs(Variables);
    createPost(Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).


+your_turn(ID, Text, ParentID, Votes, Relation, RelationAbs) : true <-
    Topics = [];
    Variables = [public(relation_abs(RelationAbs), relation(Relation), votes(Votes))];
    ia.saveLogs(Variables);
    comment(ParentID, Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).