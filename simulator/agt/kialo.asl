+your_turn(ID, Text, "", Votes, Relation) : true <-
    Topics = [];
    Variables = [votes(Votes), relation(Relation)];
    .print("POST (turn ", ID, ")");
    createPost(Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).


+your_turn(ID, Text, ParentID, Votes, Relation) : true <-
    Topics = [];
    Variables = [votes(Votes), relation(Relation)];
    .print("COMMENT (turn ", ID, ")");
    comment(ParentID, Topics, Variables, Text);
    .send(kialo_orchestrator, tell, next(ID)).