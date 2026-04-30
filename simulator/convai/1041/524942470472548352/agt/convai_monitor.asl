/* ==========================================================
    CoNVaI Monitor Agent

    Termination conditions:
        1. Hard cap:   every agent has reported max_cycles_reached
        2. Inactivity: every agent has reported idle_limit_reached
                       and none have since sent still_active

    The monitor reacts to three events sent by agents:

        idle_limit_reached(AgentName)
            Agent's consecutive idle cycles exceeded X.
            Added to idle_done set.

        still_active(AgentName)
            Agent acted again after declaring idle done.
            Removed from idle_done set.

        max_cycles_reached(AgentName)
            Agent's cycle counter exceeded T.
            Added to cycle_done set. Never retracted since
            cycles only go forward.

    Termination fires when either set contains all known agents.

    Parameters:
        total_agents(N) - total number of agents in the simulation
   ========================================================== */

+idle_limit_reached(Agent): total_agents(N) <-
    ia.save_logs([info("Agent declared idle limit reached."), agent(Agent)]);
    if (not idle_done(Agent)) {
        +idle_done(Agent)
    };
    !check_termination(N).

+still_active(Agent) <-
    ia.save_logs([info("Agent became active again."), agent(Agent)]);
    if (idle_done(Agent)) {
        -idle_done(Agent)
    }.


+max_cycles_reached(Agent): total_agents(N) <-
    ia.save_logs([info("Agent declared max cycles reached."), agent(Agent)]);
    if (not cycle_done(Agent)) {
        +cycle_done(Agent)
    };
    !check_termination(N).

+!check_termination(N) <-
    .findall(A, idle_done(A),  IdleDone);
    .findall(A, cycle_done(A), CycleDone);
    IdleCount  = .length(IdleDone);
    CycleCount = .length(CycleDone);
    ia.save_logs([idle_done(IdleCount), cycle_done(CycleCount), total(N)]);

    if (CycleCount >= N) {
        ia.save_logs([info("Termination: all agents reached max cycles.")]);
        .stopMAS
    } elif (IdleCount >= N) {
        ia.save_logs([info("Termination: all agents reached idle limit.")]);
        .stopMAS
    } else {
        ia.save_logs([info("Termination conditions not yet met. Waiting.")])
    }.
