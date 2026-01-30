next(agent0, agent1).
next(agent1, agent2).
next(agent2, agent3).
next(agent3, agent4).
next(agent4, agent5).
next(agent5, agent6).
next(agent6, agent7).
next(agent7, agent8).
next(agent8, agent9).
next(agent9, agent0).

current_turn(agent0).
last_agent(agent9).

!start_round_robin.

+!start_round_robin : 
    current_turn(Agent)
<-
    .send(Agent, tell, your_turn).

+done(Agent) : 
    last_agent(Agent) & 
    current_turn(Agent)
<-
    .broadcast(tell, finish).

+done(Agent) : 
    current_turn(Agent) &
    next(Agent, Next)
<-       
    .print("entra");            
    -+current_turn(Next);
    .send(Next, tell, your_turn). 
