#!/usr/bin/python

import ant_support

baseclass=ant_support.ant.Ant

class AutoAntWriter(baseclass):
    def __init__(self, *args, **kwargs):
        baseclass.__init__(self, *args, **kwargs)
        self.open_ants('autoant.ants')
        self.last_time=0

    def open_ants(self, filename):
        class Ants(object):
            def __init__(self, filename):
                self.filename=filename
            def write(self, data):
                self.fd.write(data.replace('\n','\r\n'))
            def __getattr__(self,att):
                if att=="fd": # lazy open
                    self.fd=open(filename,'w')
                    print >>self,'###ANT_SCRIPT_VERSION: 0.01'
                return getattr(self.fd,att)

        self.ants=Ants(filename)

    def ants_write(self, data):
        self.ants.write(s.replace('\n','\r\n'))

    def send_message(self, id, data):
        m=self.interpret_message(id,data)
        if m:
            out="w "+"".join("[%02X]"%ord(x) for x in m.last_message)
            out+=" # >>> "

            if m.name=="set_network":
                print >>self.ants,"w [46][01][__][__][__][__][__][__][__][__] # >>> 'set_network'"
            elif m.isrepeat:
                print >>self.ants,out+m.name+" (repeat)"
            else:
                pad="#"+(" "*(len(out)-6))+"  |> "
                print >>self.ants,out+m.pprint(pad)
            self.last_time=m['dt']
            print >>self.ants
        else:
            raise
        self.ants.flush()
        return baseclass.send_message(self,id,data)

    def receive_message(self, *args, **kwargs):
        m=baseclass.receive_message(self, *args, **kwargs)
        pm=self.dirty_hack_message_replace(m)
        if pm:
            pause=100+int(1000*(pm['dt']-self.last_time))
            out="r%d "%pause+"".join("[%02X]"%ord(x) for x in pm.last_message)+" # <<< "
            if pm.isrepeat:
                print >>self.ants,out+pm.name+" (repeat)"
            else:
                pad="#"+(" "*(len(out)-6))+"  |< "
                print >>self.ants,out+pm.pprint(pad)
            self.last_time=m['dt']
            print >>self.ants
        return m

    def dirty_hack_message_replace(self,m):
        if m.name in ['startup_message','capabilities_extended','channel_in_wrong_state']:
            pause=100+int(1000*(m['dt']-self.last_time))
            print >>self.ants,"p%d"%pause
            return None
        elif m.name in ['ack_data']:
            return None
        else:
            return m
