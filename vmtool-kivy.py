from threading import Thread
from datetime import date

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.dropdown import DropDown
from kivy.uix.gridlayout import GridLayout
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.textinput import TextInput

from FuncLib import *

Window.size = (dp(630), dp(210))


class MainTabs(TabbedPanel):
    status_bar = StringProperty("Idle...")
    progress_bar = NumericProperty(0)
    vm_object = None
    host_object = None

    def __init__(self, data: DataTree, **kwargs):
        super(MainTabs, self).__init__(**kwargs)
        self.dataset = data

    def start_connect(self):
        t = Thread(target=self.connect)
        t.start()
        t.join()
        self.build_lists()

    def connect(self):
        self.status_bar = "Connecting..."
        make_connection(dataset=self.dataset,
                        fqdn=self.ids.address.text,
                        user=self.ids.username.text,
                        passwd=self.ids.password.text)
        # get all content
        if self.dataset.connection is None:
            self.status_bar = "Idle..."
            return
        self.status_bar = "Getting Content..."
        self.dataset.content = self.dataset.connection.RetrieveContent()

        # VM View
        self.status_bar = "Getting Views..."
        self.dataset.vmobjlist = self.dataset.content.viewManager.CreateContainerView(
            self.dataset.content.rootFolder,
            [vim.VirtualMachine], True)
        # Hosts View
        self.dataset.hostobjlist = self.dataset.content.viewManager.CreateContainerView(
            self.dataset.content.rootFolder,
            [vim.HostSystem], True)
        # Datastore View
        self.dataset.datastoreobjlist = self.dataset.content.viewManager.CreateContainerView(
            self.dataset.content.rootFolder,
            [vim.Datastore], True)

        # Network View
        self.dataset.networkobjlist = self.dataset.content.viewManager.CreateContainerView(
            self.dataset.content.rootFolder,
            [vim.Network], True)

        # DVSwitch View
        self.dataset.dvswitchobjlist = self.dataset.content.viewManager.CreateContainerView(
            self.dataset.content.rootFolder,
            [vim.DistributedVirtualSwitch], True)

        # build dictionaries
        self.status_bar = "Building Host Dictionary..."
        for host in self.dataset.hostobjlist.view:
            self.dataset.hostdict[host.name] = host
        self.status_bar = "Building Datastore Dictionary..."
        for ds in self.dataset.datastoreobjlist.view:
            self.dataset.datastoredict[ds.name] = ds
        self.status_bar = "Building DVSwitch Dictionary..."
        for dvs in self.dataset.dvswitchobjlist.view:
            self.dataset.dvswitchdict[dvs.name] = dvs
        # build VM dict
        self.status_bar = "Building VM Dictionary..."
        obj_specs: list = list()
        for vm in self.dataset.vmobjlist.view:
            obj_spec = vmodl.query.PropertyCollector.ObjectSpec(obj=vm)
            obj_specs.append(obj_spec)
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = obj_specs
        prop_set = vmodl.query.PropertyCollector.PropertySpec(all=False)
        prop_set.type = vim.VirtualMachine
        prop_set.pathSet = ['name']
        filter_spec.propSet = [prop_set]
        prop_collector = self.dataset.content.propertyCollector
        options = vmodl.query.PropertyCollector.RetrieveOptions()
        results = list()
        try:
            result = prop_collector.RetrievePropertiesEx([filter_spec], options)
            results.append(result)
            while result.token is not None:
                result = prop_collector.ContinueRetrievePropertiesEx(result.token)
                results.append(result)
            for result in results:
                for obj in result.objects:
                    self.dataset.vmdict[obj.propSet[0].val] = obj.obj
        except vmodl.fault.ManagedObjectNotFound:
            pass

        # build net dict
        self.status_bar = "Building DVPortgroup Dictionary..."
        net_specs = list()
        for net in self.dataset.networkobjlist.view:
            net_spec = vmodl.query.PropertyCollector.ObjectSpec(obj=net)
            net_specs.append(net_spec)
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = net_specs
        prop_set = vmodl.query.PropertyCollector.PropertySpec(all=False)
        prop_set.pathSet = ['name']
        prop_set.type = vim.Network
        filter_spec.propSet = [prop_set]
        prop_collector = self.dataset.content.propertyCollector
        options = vmodl.query.PropertyCollector.RetrieveOptions()
        try:
            result = prop_collector.RetrievePropertiesEx([filter_spec], options)
            results.clear()
            results.append(result)
            while result.token is not None:
                result = prop_collector.ContinueRetrievePropertiesEx(result.token)
                results.append(result)
            for result in results:
                for obj in result.objects:
                    self.dataset.dvportgroupdict[obj.propSet[0].val] = obj.obj
        except vmodl.fault.ManagedObjectNotFound:
            pass

    def build_lists(self):
        # populate VM List
        num_of_vms = len(list(self.dataset.vmdict.keys()))
        # change height of list based on number of VMs
        self.ids.vm_list.height = dp(num_of_vms * 30)
        button_number = 0
        for vm_name in sorted(list(self.dataset.vmdict.keys()), key=str.lower):
            self.status_bar = "Creating VM List..."
            tb = Button(text=vm_name, size_hint_y=None, height=dp(30))
            tb.bind(on_release=self.vm_select)
            self.ids.vm_list.add_widget(tb)
            button_number += 1
            self.progress_bar = button_number / num_of_vms

        # do the same thing for hosts
        num_of_hosts = len(list(self.dataset.hostdict.keys()))
        self.ids.host_list.height = dp(num_of_hosts * 30)
        button_number = 0
        for host_name in sorted(list(self.dataset.hostdict.keys()), key=str.lower):
            b = Button(text=host_name, size_hint_y=None, height=dp(30))
            b.bind(on_release=self.host_select)
            self.ids.host_list.add_widget(b)
            button_number += 1

        self.status_bar = 'Done'
        return

    def disconnect(self):
        self.status_bar = 'Disconnecting...'
        Disconnect(self.dataset.connection)
        self.ids.vm_list.clear_widgets()
        self.ids.host_list.clear_widgets()
        self.dataset.clear_data()
        self.status_bar = 'Idle...'
        self.progress_bar = 0
        return

    def vm_select(self, instance):
        # set vm object for class
        self.vm_object = self.dataset.vmdict.get(instance.text)

        # fill status fields
        self.ids.num_of_cpu.text = get_num_processors(vmobj=self.vm_object)
        self.ids.cpu_usage.text = get_cpu_usage(vm=self.vm_object)
        self.ids.memory_usage.text = get_memory_usage(vm=self.vm_object)
        self.ids.total_memory.text = get_total_mem(vmobj=self.vm_object)
        self.ids.disk_usage.text = get_disk_usage(vm=self.vm_object)
        self.ids.powered_on.text = str(is_powered_on(vm=self.vm_object))
        self.ids.frozen.text = str(is_frozen(vm=self.vm_object))
        self.ids.num_of_disks.text = get_num_disks(vm=self.vm_object)
        self.ids.num_of_snapshots.text = get_num_snapshots(vm=self.vm_object)
        self.ids.num_of_files_per_disk.text = get_num_disk_files(vm=self.vm_object)
        self.ids.swapped_memory.text = get_swapped_ram(vmobj=self.vm_object)
        self.ids.host_name.text = get_host_name(vmobj=self.vm_object)
        return

    def host_select(self, instance):
        # set host object for class
        self.host_object = self.dataset.hostdict.get(instance.text)
        # get stats
        self.ids.host_cpu.text = str(get_host_cpu_usage(hostobj=self.host_object)) + ' %'
        self.ids.cpu_bar.value = get_host_cpu_usage(hostobj=self.host_object)
        self.ids.host_mem.text = str(get_host_memory_usage(hostobj=self.host_object)) + ' %'
        self.ids.mem_bar.value = get_host_memory_usage(hostobj=self.host_object)
        self.ids.storage_free.text = str(get_host_storage_usage(hostobj=self.host_object)) + ' %'
        self.ids.storage_bar.value = get_host_storage_usage(hostobj=self.host_object)
        self.ids.host_powered_on.text = str(is_host_powered_on(hostobj=self.host_object))
        self.ids.host_maintenance_mode.text = str(is_host_in_maint_mode(hostobj=self.host_object))
        return

    def power_on_vm(self):
        res = power_on_vm(self.vm_object)
        if res:
            pop = Popup(title="Info", content=Label(text='Power On Sent'), size_hint=(.2, .2),)
            pop.open()
        return

    def task_view(self):
        task_manager = self.dataset.content.taskManager
        filter_spec = vim.TaskFilterSpec()
        by_entity = vim.TaskFilterSpec.ByEntity()
        if self.vm_object is None:
            pop = Popup(title="Error", content=Label(text='Select a VM first.'), size_hint=(.2, .2), )
            pop.open()
            return
        by_entity.entity = self.vm_object
        by_entity.recursion = 'self'
        filter_spec.entity = by_entity
        task_collector = task_manager.CreateCollectorForTasks(filter=filter_spec)

        # create inner class for tasks
        class TaskObj:
            def __init__(self):
                self.start_date = None
                self.state = None
                self.description_id = None
                self.start_time = None
                self.complete_time = None
                self.time_to_complete = None
                self.progress = None

        # init list of task objects
        task_objs = list()
        # package tasks in objects and append to list
        mv = ModalView(size_hint=(.9, .8))
        gl = GridLayout(cols=7)
        for task in task_collector.latestPage:
            tmp_obj = TaskObj()
            tmp_obj.start_date = str(task.startTime.date())
            tmp_obj.state = task.state
            tmp_obj.description_id = task.descriptionId
            tmp_obj.start_time = str(task.startTime.time())[:str(task.startTime.time()).rfind('.')]
            if task.completeTime is not None:
                tmp_obj.complete_time = str(task.completeTime.time())[:str(task.completeTime.time()).rfind('.')]
                tmp_obj.time_to_complete = task.completeTime - task.startTime
                tmp_obj.time_to_complete = str(tmp_obj.time_to_complete)[:str(tmp_obj.time_to_complete).rfind('.')]
                tmp_obj.progress = 100
            else:
                tmp_obj.complete_time = 0
                tmp_obj.time_to_complete = 0
                tmp_obj.progress = task.progress
            task_objs.append(tmp_obj)
        gl.add_widget(Label(text="Start Date", underline=True))
        gl.add_widget(Label(text="State", underline=True))
        gl.add_widget(Label(text="Description ID", underline=True))
        gl.add_widget(Label(text="Start Time", underline=True))
        gl.add_widget(Label(text="Complete Time", underline=True))
        gl.add_widget(Label(text="Time to Complete", underline=True))
        gl.add_widget(Label(text="Progress", underline=True))
        for i in range(len(task_objs)):
            gl.add_widget(Label(text=str(task_objs[i].start_date)))
            gl.add_widget(Label(text=str(task_objs[i].state)))
            gl.add_widget(Label(text=str(task_objs[i].description_id)))
            gl.add_widget(Label(text=str(task_objs[i].start_time)))
            gl.add_widget(Label(text=str(task_objs[i].complete_time)))
            gl.add_widget(Label(text=str(task_objs[i].time_to_complete)))
            gl.add_widget(Label(text=str(task_objs[i].progress)))
        mv.add_widget(gl)
        mv.open()
        return

    def power_off_vm(self):
        res = poweroff_vm(self.vm_object)
        if res:
            pop = Popup(title="Info", content=Label(text='Power Off Sent'), size_hint=(.2, .2))
            pop.open()
        return

    def rename_vm(self):
        mv = ModalView(size_hint=(.5, .5))
        bl = BoxLayout(orientation='vertical')
        bl.add_widget(Label(text='Enter a new name.'))
        ti = TextInput(multiline=False, text=self.vm_object.name)
        bl.add_widget(ti)

        def rn(instance):
            rename_obj(self.vm_object, ti.text, self.dataset)
            mv.dismiss()
            return

        b = Button(text='Rename')
        bl.add_widget(b)
        mv.add_widget(bl)
        b.bind(on_release=rn)
        mv.open()
        p = Popup(title='Info', content=Label(text="Rename task sent."), size_hint=(.2, .2))
        p.open()
        return

    def promote_vm(self):
        promote_clone(vmobj=self.vm_object)
        p = Popup(title='Info', content=Label(text="Promote task sent."), size_hint=(.2, .2))
        p.open()
        return

    def clone_vm(self):
        mv = ModalView(size_hint=(.5, .5))
        bl = BoxLayout(orientation='vertical')
        bl.add_widget(Label(text='Enter a new name.'))
        ti = TextInput(multiline=False, text=self.vm_object.name)
        bl.add_widget(ti)

        def clone(instance):
            clone_vm(self.vm_object, ti.text)
            mv.dismiss()
            return

        b = Button(text='Clone')
        bl.add_widget(b)
        mv.add_widget(bl)
        b.bind(on_release=clone)
        mv.open()
        p = Popup(title='Info', content=Label(text="Clone task sent."), size_hint=(.2, .2))
        p.open()
        return

    def create_snapshot(self):
        mv = ModalView(size_hint=(.7, .7))
        bl = BoxLayout(orientation='vertical')
        bl.add_widget(Label(text='Snapshot Name'))
        d = date
        name = TextInput(multiline=False, text=str(d.today()))
        bl.add_widget(name)
        bl.add_widget(Label(text='Description'))

        description = TextInput()
        bl.add_widget(description)
        bl.add_widget(Label(text='Snapshot Memory?'))
        memory = CheckBox(color=(0, 0, 1, 1))
        bl.add_widget(memory)
        bl.add_widget(Label(text='Quiesce Disks?'))
        quiesce = CheckBox(color=(0, 0, 1, 1))
        bl.add_widget(quiesce)

        def cs(instance):
            create_snapshot(snapshot_name=name.text, vm=self.vm_object, snapshot_desc=description.text,
                            snapshot_memory=memory.active, snapshot_quiesce=quiesce.active)
            mv.dismiss()
            p = Popup(title='Info', content=Label(text="Snapshot task sent."), size_hint=(.2, .2))
            p.open()
            return

        b = Button(text='Snapshot')
        bl.add_widget(b)
        mv.add_widget(bl)
        b.bind(on_release=cs)
        mv.open()
        return

    def migrate_vm(self):
        dsdict = dict()

        mv = ModalView(size_hint=(.8, .8))
        bl1 = BoxLayout(orientation='vertical')
        sv = ScrollView()
        bl1.add_widget(sv)
        bl = BoxLayout(orientation='vertical')
        sv.add_widget(bl)

        def mig1(instance):
            self.host_object = self.dataset.hostdict.get(instance.text)
            bl.clear_widgets()
            for ds in self.host_object.datastore:
                dsdict[ds.name] = ds
                but = Button(text=ds.name)
                but.bind(on_release=mig2)
                bl.add_widget(but)
        # add hosts
        for host_name in sorted(list(self.dataset.hostdict.keys())):
            b = Button(text=host_name)
            b.bind(on_release=mig1)
            bl.add_widget(b)
        mv.add_widget(bl1)
        mv.open()

        def mig2(instance):
            migrate_vm(vmobj=self.vm_object, hostobj=self.host_object, dsobj=dsdict.get(instance.text))
            mv.dismiss()
        return

    def linked_clone(self):
        res = make_linked_clone(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Linked Clone task sent."), size_hint=(.2, .2))
            p.open()
        return

    def delete_vm(self):
        res = delete_vm(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Delete task sent."), size_hint=(.2, .2))
            p.open()
        return

    def instant_clone(self):
        res = make_instant_clone(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Instant Clone task sent."), size_hint=(.2, .2))
            p.open()
        return

    def freeze_vm(self):
        # define script object
        class FreezeScript:
            def __init__(self):
                self.script_file_name = ''
                self.script_content = r''

        # instantiate script objects
        windows_reboot_script = FreezeScript()
        windows_fast_script = FreezeScript()
        linbsd_reboot_script = FreezeScript()

        # define scripts
        windows_reboot_script.script_file_name = "freeze.bat"
        windows_reboot_script.script_content = r'"C:\Program Files\VMware\VMware Tools\rpctool.exe" "instantclone.freeze" && shutdown /r /t 001'
        windows_fast_script.script_file_name = 'fast-freeze.ps1'
        windows_fast_script.script_content = r'cd "C:\Program Files\VMware\VMware Tools"; .\rpctool.exe "instantclone.freeze"; ping 127.0.0.1; Get-NetAdapter | Enable-NetAdapter; shutdown /l > output'
        linbsd_reboot_script.script_file_name = 'freeze.sh'
        linbsd_reboot_script.script_content = r'vmware-rpctool "instantclone.freeze" && init 6'

        # define script dictionary
        script_dictionary = {
            "Windows Restart Script": windows_reboot_script,
            "Windows Fast Script": windows_fast_script,
            "Linux/BSD Restart Script": linbsd_reboot_script
        }

        # define widgets
        mv = ModalView(size_hint=(.4, .5))
        bl = BoxLayout(orientation='vertical')
        dd = DropDown()

        def dd_choose(instance):
            dd.select(instance.text)
            return

        for i in list(script_dictionary.keys()):
            b = Button(text=i, size_hint_y=None, height=dp(40))
            b.bind(on_release=dd_choose)
            dd.add_widget(b)
        ddb = Button(text='Select Freeze Script', size_hint_y=None, height=dp(40))
        ddb.bind(on_release=dd.open)

        def dd_select(instance, x):
            setattr(ddb, "text", x)
            return

        dd.bind(on_select=dd_select)
        bl.add_widget(ddb)
        bl.add_widget(Label(text='Username', size_hint_y=None, height=dp(40)))
        username = TextInput(multiline=False, size_hint_y=None, height=dp(40))
        bl.add_widget(username)
        bl.add_widget(Label(text='Password', size_hint_y=None, height=dp(40)))
        password = TextInput(multiline=False, password=True, size_hint_y=None, height=dp(40))
        bl.add_widget(password)

        def freeze_button_handler(instance) -> None:
            script_type: str = ddb.text
            script_file_obj: FreezeScript = script_dictionary.get(script_type)
            script_user: str = username.text
            script_password: str = password.text

            ret = freeze_vm(script_type=script_type,
                            user=script_user,
                            password=script_password,
                            file_name=script_file_obj.script_file_name,
                            file_content=script_file_obj.script_content,
                            data=self.dataset,
                            vm=self.vm_object)
            # a return value greater than 0 means success
            if ret > 0:
                mv.dismiss()
                p = Popup(title='Info', content=Label(text="Freeze Script Started."), size_hint=(.2, .2))
                p.open()
            else:
                mv.dismiss()
                p = Popup(title='Info', content=Label(text="Freeze not started."), size_hint=(.2, .2))
                p.open()

        freeze_button = Button(text="Freeze VM")
        freeze_button.bind(on_release=freeze_button_handler)
        bl.add_widget(freeze_button)
        mv.add_widget(bl)
        mv.open()
        # handlers

        return

    def bios_boot(self):
        bios_boot(vm=self.vm_object)
        p = Popup(title='Info', content=Label(text="Bios boot task sent."), size_hint=(.2, .2))
        p.open()
        return

    def reset_vm(self):
        res = reset_vm(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Reset task sent."), size_hint=(.2, .2))
            p.open()
        return

    def reboot_vm_guest(self):
        res = reboot_vm_guest(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Reboot task sent."), size_hint=(.2, .2))
            p.open()
        return

    def shutdown_vm_guest(self):
        res = shutdown_vm(vmobj=self.vm_object)
        if res:
            p = Popup(title='Info', content=Label(text="Shutdown task sent."), size_hint=(.2, .2))
            p.open()
        return

    def screen_size(self):
        set_screen_resolution(vmobj=self.vm_object, width=1280, height=960)
        p = Popup(title='Info', content=Label(text="Screen Resolution Set."), size_hint=(.2, .2))
        p.open()
        return

    def refresh_list(self):
        self.disconnect()
        self.start_connect()
        self.build_lists()
        p = Popup(title='Info', content=Label(text="List Refreshed."), size_hint=(.2, .2))
        p.open()
        return


class VmtoolKivy(App):
    def build(self):
        return MainTabs(data=self.dataset)

    def __init__(self, data: DataTree, **kwargs):
        super().__init__(**kwargs)
        self.dataset = data


def main():
    datatree = DataTree.get_instance()
    VmtoolKivy(data=datatree).run()
    return


if __name__ == '__main__':
    main()
