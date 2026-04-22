!start.

+!start: true <- 
    createLink("social_agent").

+follows(Agent): true <- 
    .print("Now following ", Agent).

+followed_by(Agent): true <- 
    .print("Now followed by ", Agent).