# WORKING!!!!!!
import sys
import win32com.client
import time
import threading
import pythoncom
import can_signals_enum
import help_utils
from win32gui import MessageBox as msgbox
from win32api import Sleep as wait


sys.coinit_flags = 0
# CANalyzer Event Class **************
class MeasEvents:

    def __init__(self):

        self.CAPL1 = None
        self.CAPL2 = None
        self.Appl = None
        self.CaplFunction1 = None
        self.CaplFunction2 = None
        print "when?", self.Appl
        self.init_flag = False


    def OnInit(self):
        print "parent MeasEvents:OnInit now called"
        print "noW?", self.Appl
        print self.CAPL2, self.CAPL1
        if self.CAPL1 is not None and self.CAPL2 is not None:
            self.CaplFunction1 = self.Appl.CAPL.GetFunction(self.CAPL1)
            self.CaplFunction2 = self.Appl.CAPL.GetFunction(self.CAPL2)
            self.CaplFunction1 = win32com.client.Dispatch(self.CaplFunction1)
            self.CaplFunction2 = win32com.client.Dispatch(self.CaplFunction2)
            #self.CaplFunction1 = self.Appl.CAPL.GetFunction("testDiag")
            #self.CaplFunction2 = self.Appl.CAPL.GetFunction("t2")
            print "OnInit:Load CAPL Script = " + self.CAPL1 + self.CAPL2
            self.init_flag = True


# User Class **************
class InitiateCanalyzer:
    def __init__(self, event_thread, can_logs=None, delta_flag=False, app_id=None):
        # app = win32com.client.DispatchEx('CANalyzer.Application')
        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch(
            pythoncom.CoGetInterfaceAndReleaseStream(
                app_id,
                pythoncom.IID_IDispatch
            )
        )
        self.Measurement = self.app.Measurement
        self.Running = lambda: self.Measurement.Running
        self.event = event_thread
        self.can_logs = can_logs  # It's a list
        self.delta_flag = delta_flag
        self.marshalled_app_id = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, self.app)
        # Used to call MeasEvent to call CAPL function, but time.sleep() will cause CANalyzer stuck
        # Besides, it has to be called before CANalyzer start?

        self.__MeasurementEvents = win32com.client.DispatchWithEvents(self.Measurement, MeasEvents)
        print self.__MeasurementEvents

        # transfer the application object to Event class for CAPL handling
        print 'which is first'
        self.__MeasurementEvents.Appl = self.app

    def start(self):
        if not self.Running():
            self.Measurement.Start() # when CANalyzer is down and has error, it will throw
            # com_error: (-2147352567, 'Exception occurred.', (0, u'Measurement::Start', u'User interface is busy',
            # u'C:\\Program Files\\Vector CANalyzer 10.0\\Help01\\CANoeCANalyzer.chm', 4270, -2147418113), None)

    def stop(self):
        if self.Running():
            self.Measurement.Stop()

    def get_can_log(self):
        if self.can_logs is None:
            self.can_logs = "NULL"
        return self.can_logs

    def verify_no_fault_on_start(self,
                                 signal_1="EmgcyCallFalt_B_Dsply",
                                 message_1="TCU_Send_Signals_5"
                                 ):
        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch(
            pythoncom.CoGetInterfaceAndReleaseStream(
                self.marshalled_app_id,
                pythoncom.IID_IDispatch
            )
        )
        print('going to verify, sleep 15 s first to wait clear DTC')
        start_time = time.time()
        while True:
            if self.app.Bus.GetSignal(2, message_1, signal_1).Value == 1.0:
                print('fault, should not start testing')
                return False
            elif self.app.Bus.GetSignal(2, message_1, signal_1).Value == 0.0:
                if time.time() - start_time > 15:
                    print('no fault, ready to start testing')
                    return True

    def get_a_signal(self, signal_queue, gui_queue, result_queue, oecon_list=None, ts_instance=None,
                     can_bus=2, signal="EmgcyCallHmi_D_Stat", msg="TCU_Send_Signals_5",
                     enum=None, verify_queue=None):
        """
        Select one signal to monitor and pass to ts_instance.
        :param ts_instance: Choose test suite
        :param signal_queue: Pass signal values to test suite instance. tuple (signal_status, delta_time)
        :param gui_queue: Update GUI
        :param can_bus: CAN BUS Channel
        :param oecon_list: oecon info, passed to ts_instance
        :param signal: signal user defined
        :param msg: signal related message
        :param enum: if not None, it should be related to the signal.
        :return:
        """
        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch(
            pythoncom.CoGetInterfaceAndReleaseStream(
                self.marshalled_app_id,
                pythoncom.IID_IDispatch
            )
        )
        temp_status = -10.0
        prev_time = time.time()
        count_1 = 0
        while True:
            time.sleep(0.1)
            current_status = self.app.Bus.GetSignal(can_bus, msg, signal).RawValue

            if temp_status != current_status:
                count_1 += 1
                current_time = time.time()

                delta_time, prev_time = current_time - prev_time, current_time
                temp_status = current_status
                # print "current status put to queue:", current_status
                signal_queue.put((current_status, delta_time))

                if verify_queue:
                    verify_queue.put((current_status, delta_time))

                if enum:
                    for name, member in enum.__members__.items():
                        if current_status == member.value:
                            current_status = member
                else:
                    # if not implemented in enum, should convert integer to readable CAN msg values.
                    current_status = help_utils.decode_raw_signal_value_helper(current_status)
                gui_queue.put(str(current_status) + " is changed in " + str(delta_time) + "s.")

                # pass signal value to test suite
                if ts_instance:
                    ts_instance.ts_start(signal_queue, gui_queue, result_queue, oecon_list)

            if self.event.wait(timeout=0.01):
                pythoncom.CoUninitialize()
                break

    def get_a_signal_2(self):
        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch(
            pythoncom.CoGetInterfaceAndReleaseStream(
                self.marshalled_app_id,
                pythoncom.IID_IDispatch
            )
        )

        temp_status = -10.0

        prev_time = time.time()

        count_1 = 0
        while True:
            time.sleep(1)
            current_status = self.app.Bus.GetSignal(2, "TesterPhysicalResTCU4_Copy_3",
                                                            "TesterPhysicalResTCU_3").RawValue
            #current_status = self.app.Bus.GetSignal(2, "TesterPhysicalResTCU4",
             #                                               "TesterPhysicalResTCU").RawValue
            # signal_current_log_1.append("oh " + signal_enum_1.name() + " status: " + str(current_status))
            if current_status >0:
                print current_status
                break
            '''
            if temp_status != current_status:
                count_1 += 1
                current_time = time.time()
                delta_time, prev_time = current_time - prev_time, current_time
                temp_status = current_status
                print("curr status: {} and delta time: {} at: {}".format(
                    current_status, delta_time, current_time))
            '''

    def get_all_signals(self, queue_from_gui, signal_enum_1, signal_1, message_1,
                        signal_enum_2=can_signals_enum.IgnStatus,
                        signal_2="Ignition_Status", message_2="BodyInfo_3_HS4"):

        pythoncom.CoInitialize()
        self.app = win32com.client.Dispatch(
            pythoncom.CoGetInterfaceAndReleaseStream(
                self.marshalled_app_id,
                pythoncom.IID_IDispatch
            )
        )

        temp_status = -10.0
        temp_status_2 = -10.0
        prev_time = time.time()
        prev_time_2 = time.time()
        signal_delta_log_1 = list()
        signal_delta_log_1.append("\n" + signal_enum_1.name() + " status: ")
        # signal_delta_log_1.append(signal_enum_1.name() + " status: default -> ")
        signal_delta_log_2 = list()
        signal_delta_log_2.append("\n" + signal_enum_2.name() + " status: ")
        # signal_delta_log_2.append(signal_enum_2.name() + " status: default -> ")
        signal_current_log_1 = list()
        signal_current_log_1.append(signal_enum_1.name() + " status: ")
        # signal_current_log_1.append(signal_enum_1.name() + " status: default")
        signal_current_log_2 = list()
        signal_current_log_2.append(signal_enum_2.name() + " status: ")
        # signal_current_log_2.append(signal_enum_2.name() + " status: default")
        count_1 = 0
        while True:
            time.sleep(1)
            current_status = self.app.Bus.GetSignal(2, message_1, signal_1).Value
            # signal_current_log_1.append("oh " + signal_enum_1.name() + " status: " + str(current_status))
            if temp_status != current_status:
                count_1 += 1
                current_time = time.time()
                delta_time, prev_time = current_time - prev_time, current_time
                temp_status = current_status
                for name, member in signal_enum_1.__members__.items():
                    if current_status == member.value:
                        current_status = member
                        queue_from_gui.put("curr status: {} and delta time: {} at: {}".format(
                            current_status, delta_time, current_time))
                        print("curr status: {} and delta time: {} at: {}".format(
                            current_status, delta_time, current_time))
                        signal_delta_log_1.append(str(delta_time) + " s -> " + str(current_status) + " -> " + "({})\n".format(count_1))
                        signal_current_log_1.append(" -> " + str(current_status) + " at: " + str(current_time) + "({})\n".format(count_1))
                        # self.can_logs.append(" -> " + str(current_status) + " at: " + str(current_time) + "\n")

            current_status_2 = self.app.Bus.GetSignal(2, message_2, signal_2).Value
            # signal_current_log_2.append("oh" + signal_enum_2.name() + " status: " + str(current_status_2))

            # by default it's ign status
            if temp_status_2 != current_status_2:
                current_time_2 = time.time()
                delta_time_2, prev_time_2 = current_time_2 - prev_time_2, current_time_2
                temp_status_2 = current_status_2
                for name, member in signal_enum_2.__members__.items():
                    if current_status_2 == member.value:
                        current_status_2 = member
                        queue_from_gui.put("curr status: {} and delta time: {} at: {}".format(
                            current_status_2, delta_time_2, current_time_2))
                        print("curr status: {} and delta time: {} at: {}".format(
                            current_status_2, delta_time_2, current_time_2))
                        signal_delta_log_2.append(str(delta_time_2) + " s -> " + str(current_status_2) + " -> " + "\n")
                        signal_current_log_2.append(" -> " + str(current_status_2) + " at: " + str(current_time_2)
                                                    + "\n")
                        # self.can_logs.append(" -> " + str(current_status_2) + "at: " + str(current_time_2) + "\n")
            if self.event.wait(timeout=0.01):
                # print("received stop: {}".format(time.ctime()))         # 4) 15:31:20
                if not self.delta_flag:
                    if self.can_logs is not None:
                        self.can_logs = self.can_logs + signal_current_log_1 + signal_current_log_2
                        print("get current")
                else:
                    if self.can_logs is not None:
                        self.can_logs = self.can_logs + signal_delta_log_1 + signal_delta_log_2
                        self.can_logs.append('\n')
                        print("get delta")
                pythoncom.CoUninitialize()
                break
                # print("can_logs length: {}".format(self.can_logs[0]))

    def marshal_handler_1(self):
        if self.Running():
            call_marshal_id = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch,
                                                                              self.__MeasurementEvents.CaplFunction1)
            print 'call id:', call_marshal_id  # .__repr__
            return call_marshal_id

    def marshal_handler_2(self):
        if self.Running():
            call_marshal_id = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch,
                                                                              self.__MeasurementEvents.CaplFunction2)
            print 'call id:', call_marshal_id  # .__repr__
            return call_marshal_id

    def select_capl_function(self, function_name_1, function_name_2):
        print "when select first"
        self.__MeasurementEvents.CAPL1 = function_name_1
        self.__MeasurementEvents.CAPL2 = function_name_2

        print "select end"

    # !!! Remember in CAPL, the para1 should set to LONG, not INT !!!
    def execute_capl_function2(self, call_marshal_id, par1=None, par2=None, par3=None, par4=None):
        # if call this func in another thread, self.Running will be considered not CoInitiate.
        # pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)s
        pythoncom.CoInitialize()
        measurement_event = pythoncom.CoGetInterfaceAndReleaseStream(
            call_marshal_id,
            pythoncom.IID_IDispatch
        )
        m = win32com.client.Dispatch(measurement_event)
        # m = win32com.client.getevents('{A8507FAB-33D6-43C5-B9F5-3B74451A4C41}')

        # m = win32com.client.WithEvents(self.Measurement, MeasEvents)
        print "Now trying to call CAPL func now"
        #print "run?", self.Running()
        while True:
                print 'y'
                pythoncom.PumpWaitingMessages()
                if par1 == None:
                    ret = m.Call()
                    print "ret is {}".format(ret)
                    pythoncom.CoUninitialize()
                    return ret
                elif par2 == None:
                    ret = m.Call(par1)
                    print "ret is {}".format(ret)
                    pythoncom.CoUninitialize()
                    return ret
                elif par3 == None:
                    ret = m.Call(par1, par2)
                    print "ret is {}".format(ret)
                    pythoncom.CoUninitialize()
                    return ret
                elif par4 == None:
                    ret = m.Call(par1, par2, par3)
                    print "ret is {}".format(ret)
                    pythoncom.CoUninitialize()
                    return ret
                else:
                    ret = m.Call(par1, par2, par3, par4)
                    print "ret is {}".format(ret)
                    pythoncom.CoUninitialize()
                    return ret

    # Actually don't need this function. Only need one execute function .
    def execute_capl_function1(self, Par1=None, Par2=None, Par3=None, Par4=None, Par5=None):
        # if call this func in another thread, self.Running will be considered not CoInitiate.
        """

        Sets scalar parameter signal value

        Syntax:         devcanalyzer.
        Parameter:      Par1 - number - First parameter of CAPL function, if not needed keep to None
                        Par2 - number - Second parameter of CAPL function, if not needed keep to None
                        Par3 - number - Third parameter of CAPL function, if not needed keep to None
                        Par4 - number - Fourth parameter of CAPL function, if not needed keep to None
                        Par5 - number - Fifth parameter of CAPL function, if not needed keep to None
        Return Value:   ret - number - Return Value of the selected CAPL function
        Exceptions:
        Description:    This function can only be executed in the systemState MEASUREMENT_IDLE.
                        Use only Int variables as Parameters to avoid type mismatching.
                        It is only possible to pass 10 Parameters to one CAPL script.
                        If there is a return value it will be returned, if not the return value is None.

        """
        print "Now trying to call CAPL func now"

        # !!!!!!!!!!!!!!!!!!! IMPORTANT !!!!!!!!!!!!!!!!!!!!!!!!!
        # Notice tha the Program Node should be placed after 'Online/Offline' in configuration.
        # Otherwise, the returning value is wrong!!!!
        while True:
                #print self.__MeasurementEvents.CaplFunction
                if (Par1==None):
                    ret = self.__MeasurementEvents.CaplFunction1.Call()
                elif (Par2==None):
                    ret = self.__MeasurementEvents.CaplFunction1.Call(Par1)
                elif (Par3==None):
                    ret = self.__MeasurementEvents.CaplFunction1.Call(Par1,Par2)
                elif (Par4==None):
                    ret = self.__MeasurementEvents.CaplFunction1.Call(Par1,Par2,Par3)
                elif (Par5==None):
                    ret = self.__MeasurementEvents.CaplFunction1.Call(Par1,Par2,Par3,Par4)
                else:
                    ret = self.__MeasurementEvents.CaplFunction1.Call(Par1,Par2,Par3,Par4,Par5)
                print "ret is {}".format(ret)
                pythoncom.CoUninitialize()
                return ret


def check_hmi(logs):
    # global call_complete_flag
    hmi_status_result = ""
    for line in logs:
        print("lines: {}".format(line))
        if line.find("EmgcyCallHmi.CallCompleted") != -1:
            call_complete_flag = True
        if line.find("EmgcyCallHmi.Standby") != -1 and call_complete_flag:
            print("Found you!")
            delta = line.split("s ->")[0].strip()
            delta_int = int(float(delta))
            if delta_int == 10 or delta_int == 9:
                print("success! {}".format(delta))
                hmi_status_result = "PASS!"
            else:
                print("fail! {}".format(delta))
                hmi_status_result = "FAIL!"
            call_complete_flag = False
        else:
            print("where are you!")
            return "N/A TEST"


def check_fault(logs):
    for line in logs:
        print("each line: {}".format(line))


def write_can_to_file(current_can_logs, start_time):
    with open('can_status_list.txt', 'a+') as f:
        print("write start!")
        f.write("\n" + start_time + ":\n ")
        for line in current_can_logs:
            f.write(line)
        # f.write('\n\n')
        print("write finish!")

def main(id1, id2):
    event = threading.Event()
    listC = []
    listD = []
    import Queue
    q = Queue.Queue()
    ic = InitiateCanalyzer(event, listC, app_id=id1)
    # id = InitiateCanalyzer(event, listD, app_id=id2)
    ic.start()
    t3 = threading.Thread(target=ic.select_capl_function, name="Select-Thread",args=("testDiag", 't2'))
    t3.start()
    # ic.select_capl_function("testDiag", 't2')
    print "selected"
    #t3.join()

    ############### USE MsgWaitForMultipleObject to pump message ################
    '''
    # !!!!!!!!!!!!!! IMPORTANT to make CANalyzer not FREEZE!!!!!
    # pythoncom.PumpWaitingMessages()
    
    from win32process import beginthreadex
    from win32event import MsgWaitForMultipleObjects, QS_ALLINPUT, WAIT_OBJECT_0,CreateEvent
    # handle, ids = beginthreadex(None, 0, sleep_thread, (), 0)
    # handles = list()
    # handles.append(handle)
    ic_event_handle = CreateEvent(None,0,0,None)
    rc = MsgWaitForMultipleObjects((ic_event_handle,), 0, 5000, QS_ALLINPUT)
    start_time = time.time()
    while True:
        if rc == WAIT_OBJECT_0 + 1:
            pythoncom.PumpWaitingMessages()
            # print 'pumping'
        else:
            break
        if ic.Running():
            if time.time() - start_time > 5:
                print ic.Running()
                break
    # msgbox(0, "Measurement Started" + chr(13) + "Now CAPL is called", "Info", 16) # Another not elegant way
    '''

    help_utils.wait_and_pump_msg()
    ############### END ################

    capl_func_handler_id_1 = ic.marshal_handler_1()
    capl_func_handler_id_2 = ic.marshal_handler_2()

    threading.Thread(target=ic.execute_capl_function2, name="Execute-Thread1",
                     args=(capl_func_handler_id_1,22)).start()

    # id.execute_capl_function()  # IT WORKS
    time.sleep(4)
    # cause com_error: 'The application called an interface that was marshalled for a different thread.'
    threading.Thread(target=ic.execute_capl_function2, name="Execute-Thread2", args=(capl_func_handler_id_2,)).start()
    print "before sleep", time.time()

    #id.execute_capl_function2()
    # wait(10000)
    print "after sleep", time.time()
    time.sleep(5)
    print("next to stop canalyzer: {}".format(time.ctime()))  # 1) 15:31:20
    ic.stop()


def sleep_thread():
    print 'sleep/////'
    pythoncom.PumpWaitingMessages()
    time.sleep(10)


if __name__ == "__main__":

    id1 = help_utils.generate_app_marshal()
    id2 = help_utils.generate_app_marshal()

    threading.Thread(target=main, args=(id1, id2)).start()
    l = [ '213']
    r = help_utils.get_dtc_msg_from_list(l)
    print r
    '''
    event = threading.Event()
    listC = []
    listD = []
    # app = win32com.client.DispatchEx('CANalyzer.Application')
    # app.Measurement.Start()
    startTime = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    # marshalled_app = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, app)
    ic = InitiateCanalyzer(event, listC, app_id=id1)
    ic.start()
    threading.Thread(target=ic.get_a_signal).start()
    help_utils.wait_and_pump_msg()
    '''

