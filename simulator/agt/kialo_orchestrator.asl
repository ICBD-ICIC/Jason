//debate(id, author, text, parent_id, votes, relation).

/* Initial goals */
!start_debate.

/* Plans */
+!start_debate : true <-
    +current_turn(0).

+current_turn(ID) : 
    debate(ID, Agent, Text, ParentID, Votes, Relation) 
<-
    .send(Agent, tell, your_turn(Text, ParentID, Votes, Relation)).

+done(Agent) : 
    current_turn(ID)
<-                 
    -+current_turn(ID+1).
