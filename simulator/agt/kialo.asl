+your_turn(Text, "", Votes, Relation) : true <-
    Topic = [];
    Variables = [votes(Votes), relation(Relation)];
    createPost(Topics, Variables, Text);
    .send(orchestrator, tell, done(self)).

+your_turn(Text, ParentID, Votes, Relation) : true <-
    Topic = [];
    Variables = [votes(Votes), relation(Relation)];
    comment(ParentID, Topics, Variables, Text);
    .send(orchestrator, tell, done(self)).
