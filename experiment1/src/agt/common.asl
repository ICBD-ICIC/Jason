random_range_int(Min, Max, R) :-
    .random(X) &
    Y = X * (Max - Min) + Min &
    R = math.floor(Y).

initial_affectivity_non_partisan(LR, LD, HR, HD) :-
    random_range_int(0, 4, LR) &
    random_range_int(0, 4, LD) &
    random_range_int(0, 10, HR) &
    random_range_int(0, 10, HD).

initial_affectivity_republican(LR, LD, HR, HD) :-
    random_range_int(5, 10, LR) &
    random_range_int(0, 4, LD) &
    random_range_int(0, 4, HR) &
    random_range_int(0, 10, HD).

initial_affectivity_democrat(LR, LD, HR, HD) :-
    random_range_int(0, 4, LR) &
    random_range_int(5, 10, LD) &
    random_range_int(0, 10, HR) &
    random_range_int(0, 4, HD).

+!initiate_republican : 
    initial_affectivity_republican(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+!initiate_democrat : 
    initial_affectivity_democrat(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+!initiate_non_partisan : 
    initial_affectivity_non_partisan(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

/* +message(Id, Author, Content, Original, Timestamp) : 
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD) &
    love(republicans, LR) &
    love(democrats, LD) &
    hate(republicans, HR) &
    hate(democrats, HD) 
<-
    ia.updateLove(republicans, LR, PS, D, PD, Content, NewLR);
    ia.updateLove(republicans, LR, PS, D, PD, Content, NewLR);
    ia.updateLove(republicans, LR, PS, D, PD, Content, NewLR);
    ia.updateLove(republicans, LR, PS, D, PD, Content, NewLR);
    -+ */