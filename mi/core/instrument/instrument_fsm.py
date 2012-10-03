#!/usr/bin/env python

"""
@package ion.services.mi.instrument_fsm Instrument Finite State Machine
@file ion/services/mi/instrument_fsm.py
@author Edward Hunter
@brief Simple state mahcine for driver and agent classes.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

from mi.core.exceptions import InstrumentStateException

from mi.core.log import get_logger,LoggerManager
log = get_logger()

class InstrumentFSM():
    """
    Simple state mahcine for driver and agent classes.
    """

    def __init__(self, states, events, enter_event, exit_event):
        """
        Initialize states, events, handlers.
        @param states The list of states that the FSM handles
        @param events The list of events that the FSM handles
        @param enter_event The event that indicates a state is being entered
        @param exit_event The event that indicates a state is being exited
        @param err_unhandled The error code to return on unhandled event
        """

        self.states = states
        self.events = events
        self.state_handlers = {}
        self.current_state = None
        self.previous_state = None
        self.enter_event = enter_event
        self.exit_event = exit_event

    def get_current_state(self):
        """
        Return current state.
        """

        log.debug("entering InstrumentFSM.get_current_state")
        return self.current_state

    def add_handler(self, state, event, handler):
        """
        Add an event handler.
        @param state the state to handler the event in.
        @param the event to handle.
        @retval True if successful, False otherwise.
        """
        log.debug("entering InstrumentFSM.add_handler")
        if not self.states.has(state):
            return False
        
        if not self.events.has(event):
            return False

        self.state_handlers[(state,event)] = handler
        return True
        
    def start(self, state, *args, **kwargs):
        """
        Start the state machine. Initializes current state and fires the
        EVENT_ENTER event.
        @param state The state to start in.
        @param args positional arguments to pass to the handler.
        @param kwargs keyword arguments to pass to the handler.
        @retval True if successful, False otherwise.
        @raises Any exception raised by the enter handler.
        """
        log.debug("entering InstrumentFSM.start")
        if not self.states.has(state):
            return False
                
        self.current_state = state
        handler = self.state_handlers.get((state, self.enter_event), None)
        if handler:
            handler(*args, **kwargs)
        return True

    def on_event(self, event, *args, **kwargs):
        """
        Handle an event. Call the current state handler passing the event
        and paramters.
        @param event A string indicating the event that has occurred.
        @param args positional arguments to pass to the handler.
        @param kwargs keyword arguments to pass to the handler.
        @retval result from the handler executed by the current state/event pair.
        @raises InstrumentStateException if no handler for the event exists in current state.
        @raises Any exception raised by the handlers.
        """
        log.debug("entering InstrumentFSM.on_event")
        next_state = None
        result = None

        if self.events.has(event):
            handler = self.state_handlers.get((self.current_state, event), None)
            if handler:
                log.debug("InstrumentFSM.on_event calling " + str(handler))
                (next_state, result) = handler(*args, **kwargs)
            else:
                raise InstrumentStateException('Command not handled in current state.')
        else:
            raise InstrumentStateException(str(event) + " was not handled by InstrumentFSM.on_event()")

        if self.states.has(next_state):
            self._on_transition(next_state, *args, **kwargs)
                
        return result
            
    def _on_transition(self, next_state, *args, **kwargs):
        """
        Call the sequence of events to cause a state transition. Called from
        on_event if the handler causes a transition.
        @param next_state The state to transition to.
        @param args positional arguments to pass to the handler.
        @param kwargs keyword arguments to pass to the handler.
        @raises Any exception raised by the handlers.
        """
        log.debug("entering InstrumentFSM._on_transition")
        handler = self.state_handlers.get((self.current_state, self.exit_event), None)
        if handler:
            log.debug("InstrumentFSM._on_transition calling " + str(handler))
            handler(*args, **kwargs)
        self.previous_state = self.current_state
        self.current_state = next_state
        handler = self.state_handlers.get((self.current_state, self.enter_event), None)
        if handler:
            handler(*args, **kwargs)

    def get_events(self, current_state=True):
        """
        Return a list of events handled.
        @param current_state if true, return events handled in the current state only.
        @retval list of events handled.
        """
        log.debug("entering InstrumentFSM.get_events")
        events = []
        for (key, handler) in self.state_handlers.iteritems():
            state = key[0]
            event = key[1]
            if not ((event == self.enter_event) or (event == self.exit_event)):
                if current_state:
                    if (self.current_state==state):
                        if event not in events:
                            events.append(event)
                else:
                    if event not in events:
                        events.append(event)
        return events
