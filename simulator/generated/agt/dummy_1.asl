!start.

+!start: true <- 
    createLink("social_agent").

+follows(Agent): true <- 
    .print("Now following ", Agent).

+followedBy(Agent): true <- 
    .print("Now followed by ", Agent).