+your_turn(ID, Text, "", Votes, Relation) : true <-
    Topics = [];
    Variables = [votes(Votes), public(relation(Relation)), relation(Relation)];
    ia.save_logs(Variables);
    createPost(Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).


+your_turn(ID, Text, ParentID, Votes, Relation) : true <-
    Topics = [];
    Variables = [votes(Votes), public(relation(Relation)), relation(Relation)];
    ia.save_logs(Variables);
    comment(ParentID, Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).