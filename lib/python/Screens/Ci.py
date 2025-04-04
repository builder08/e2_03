from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Tools.BoundFunction import boundFunction
from Components.Sources.StaticText import StaticText
from Components.ActionMap import ActionMap
from Components.ActionMap import NumberActionMap
from Components.Label import Label
from Components.config import config, ConfigEnableDisable, ConfigSubsection, ConfigSelection, ConfigSubList, KEY_LEFT, KEY_RIGHT, KEY_0, ConfigNothing, ConfigPIN, ConfigYesNo, NoSave, ConfigBoolean
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.SystemInfo import BoxInfo
from enigma import eTimer, eDVBCI_UI
from os import remove
from os.path import exists
import Screens.Standby

forceNotShowCiMessages = False


def setCIBitrate(configElement):
	eDVBCI_UI.getInstance().setClockRate(configElement.slotid, configElement.value)


def setCIEnabled(configElement):
	eDVBCI_UI.getInstance().setEnabled(configElement.slotid, configElement.value)


def setdvbCiDelay(configElement):
	open(BoxInfo.getItem("CommonInterfaceCIDelay"), "w").write(configElement.value)
	configElement.save()


def setRelevantPidsRouting(configElement):
	open(BoxInfo.getItem(f"CI{configElement.slotid}RelevantPidsRoutingSupport"), "w").write("yes" if configElement.value else "no")


def InitCiConfig():
	config.ci = ConfigSubList()
	config.cimisc = ConfigSubsection()
	config.cimisc.cihelperenabled = ConfigEnableDisable(default=True)
	if BoxInfo.getItem("CommonInterface"):
		for slot in range(BoxInfo.getItem("CommonInterface")):
			config.ci.append(ConfigSubsection())
			config.ci[slot].enabled = ConfigYesNo(default=True)
			config.ci[slot].enabled.slotid = slot
			config.ci[slot].enabled.addNotifier(setCIEnabled, initial_call=False)
			config.ci[slot].canDescrambleMultipleServices = ConfigSelection(choices=[("auto", _("Auto")), ("no", _("No")), ("yes", _("Yes"))], default="auto")
			config.ci[slot].use_static_pin = ConfigYesNo(default=True)
			config.ci[slot].static_pin = ConfigPIN(default=0)
			config.ci[slot].show_ci_messages = ConfigYesNo(default=True)
			config.ci[slot].disable_operator_profile = ConfigYesNo(default=False)
			config.ci[slot].alternative_ca_handling = ConfigSelection(choices=[(0, _("off")), (1, _("Close CA device at programm end")), (2, _("Offset CA device index")), (3, _("Offset and close CA device"))], default=0)
			if BoxInfo.getItem(f"CI{slot}SupportsHighBitrates"):
				highBitrateChoices = [
					("normal", _("Normal")),
					("high", _("High")),
				]
				try:
					with open(f"/proc/stb/tsmux/ci{slot}_tsclk_choices") as fd:
						choices = fd.read()
						if "extra_high" in choices:
							highBitrateChoices.append(("extra_high", _("Extra High")))
				except OSError:
					pass
				config.ci[slot].highBitrate = ConfigSelection(default="high", choices=highBitrateChoices)
				config.ci[slot].highBitrate.slotid = slot
				config.ci[slot].highBitrate.addNotifier(setCIBitrate)
			if BoxInfo.getItem(f"CI{slot}RelevantPidsRoutingSupport"):
				config.ci[slot].relevantPidsRouting = ConfigYesNo(default=False)
				config.ci[slot].relevantPidsRouting.slotid = slot
				config.ci[slot].relevantPidsRouting.addNotifier(setRelevantPidsRouting)
		if BoxInfo.getItem("CommonInterfaceCIDelay"):
			config.cimisc.dvbCiDelay = ConfigSelection(default="256", choices=[("16", "16"), ("32", "32"), ("64", "64"), ("128", "128"), ("256", "256")])
			config.cimisc.dvbCiDelay.addNotifier(setdvbCiDelay)
		config.cimisc.bootDelay = ConfigSelection(default=5, choices=[(x, _("%d Seconds") % x) for x in range(16)])


class MMIDialog(Screen):
	def __init__(self, session, slotid, action, handler=eDVBCI_UI.getInstance(), wait_text="", screen_data=None):
		Screen.__init__(self, session)

		print(f"[CI] MMIDialog with action {str(action)}")

		self.mmiclosed = False
		self.tag = None
		self.slotid = slotid

		self.timer = eTimer()
		self.timer.callback.append(self.keyCancel)

		# else the skins fails
		self["title"] = Label("")
		self["subtitle"] = Label("")
		self["bottom"] = Label("")
		self["key_menu"] = StaticText(_("MENU"))
		self["entries"] = ConfigList([])

		self["actions"] = NumberActionMap(["SetupActions", "MenuActions"],
			{
				"ok": self.okbuttonClick,
				"cancel": self.keyCancel,
				"menu": self.forceExit,
				# for PIN
				"left": self.keyLeft,
				"right": self.keyRight,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal
			}, -1)

		self.action = action
		self.screen_data = screen_data

		self.is_pin_list = -1
		self.handler = handler
		if wait_text == "":
			self.wait_text = _("wait for ci...")
		else:
			self.wait_text = wait_text

		if action == 2:		# start MMI
			handler.startMMI(self.slotid)
			self.showWait()
		elif action == 3:		# mmi already there (called from infobar)
			self.showScreen()

	def addEntry(self, list, entry):
		if entry[0] == "TEXT":		# handle every item (text / pin only?)
			list.append((entry[1], ConfigNothing(), entry[2]))
		if entry[0] == "PIN":
			pinlength = entry[1]
			if entry[3] == 1:
				# masked pins:
				x = ConfigPIN(0, len=pinlength, censor="*")
			else:
				# unmasked pins:
				x = ConfigPIN(0, len=pinlength)
			x.addEndNotifier(self.pinEntered)
			self["subtitle"].setText(entry[2])
			list.append(("", x))
			self["bottom"].setText(_("Please press OK when ready"))

	def pinEntered(self, value):
		self.okbuttonClick()

	def okbuttonClick(self):
		self.timer.stop()
		if not self.tag:
			return
		if self.tag == "WAIT":
			print("[CI] do nothing - wait")
		elif self.tag == "MENU":
			print("[CI] answer MENU")
			cur = self["entries"].getCurrent()
			if cur:
				self.handler.answerMenu(self.slotid, cur[2])
			else:
				self.handler.answerMenu(self.slotid, 0)
			self.showWait()
		elif self.tag == "LIST":
			print("[CI] answer LIST")
			self.handler.answerMenu(self.slotid, 0)
			self.showWait()
		elif self.tag == "ENQ":
			cur = self["entries"].getCurrent()
			answer = str(cur[1].value)
			length = len(answer)
			while length < cur[1].getLength():
				answer = f"0{answer}"
				length += 1
			self.answer = answer
			if config.ci[self.slotid].use_static_pin.value:
				self.session.openWithCallback(self.save_PIN_CB, MessageBox, _("Would you save the entered PIN %s persistent?") % self.answer, MessageBox.TYPE_YESNO)
			else:
				self.save_PIN_CB(False)

	def save_PIN_CB(self, ret=None):
		if ret:
			config.ci[self.slotid].static_pin.value = self.answer
			config.ci[self.slotid].static_pin.save()
		self.handler.answerEnq(self.slotid, self.answer)
		self.showWait()

	def closeMmi(self):
		self.timer.stop()
		self.close(self.slotid)

	def forceExit(self):
		self.timer.stop()
		if self.tag == "WAIT":
			self.handler.stopMMI(self.slotid)
			global forceNotShowCiMessages
			forceNotShowCiMessages = True
			self.close(self.slotid)

	def keyCancel(self):
		self.timer.stop()
		if not self.tag or self.mmiclosed:
			self.closeMmi()
		elif self.tag == "WAIT":
			self.handler.stopMMI(self.slotid)
			self.closeMmi()
		elif self.tag in ("MENU", "LIST"):
			print("[CI] cancel list")
			self.handler.answerMenu(self.slotid, 0)
			self.showWait()
		elif self.tag == "ENQ":
			print("[CI] cancel enq")
			self.handler.cancelEnq(self.slotid)
			self.showWait()
		else:
			print("[CI] give cancel action to ci")

	def keyConfigEntry(self, key):
		self.timer.stop()
		try:
			self["entries"].handleKey(key)
			if self.is_pin_list == 4:
				self.okbuttonClick()
		except Exception:
			pass

	def keyNumberGlobal(self, number):
		self.timer.stop()
		if self.is_pin_list > -1:
			self.is_pin_list += 1
		self.keyConfigEntry(KEY_0 + number)

	def keyLeft(self):
		self.timer.stop()
		if self.is_pin_list > 0:
			self.is_pin_list += -1
		self.keyConfigEntry(KEY_LEFT)

	def keyRight(self):
		self.timer.stop()
		if self.is_pin_list > -1 and self.is_pin_list < 4:
			self.is_pin_list += 1
		self.keyConfigEntry(KEY_RIGHT)

	def updateList(self, list):
		List = self["entries"]
		try:
			List.instance.moveSelectionTo(0)
		except Exception:
			pass
		List.l.setList(list)

	def showWait(self):
		self.tag = "WAIT"
		self["title"].setText("")
		self["subtitle"].setText("")
		self["bottom"].setText("")
		list = []
		list.append((self.wait_text, ConfigNothing()))
		self.updateList(list)

	def showScreen(self):
		if self.screen_data is not None:
			screen = self.screen_data
			self.screen_data = None
		else:
			screen = self.handler.getMMIScreen(self.slotid)

		list = []

		self.timer.stop()
		if len(screen) > 0 and screen[0][0] == "CLOSE":
			timeout = screen[0][1]
			self.mmiclosed = True
			if timeout > 0:
				self.timer.start(timeout * 1000, True)
			else:
				self.keyCancel()
		else:
			self.mmiclosed = False
			self.tag = screen[0][0]
			for entry in screen:
				if entry[0] == "PIN":
					if config.ci[self.slotid].use_static_pin.value and str(config.ci[self.slotid].static_pin.value) != "0":
						answer = str(config.ci[self.slotid].static_pin.value)
						length = len(answer)
						while length < config.ci[self.slotid].static_pin.getLength():
							answer = f"0{answer}"
							length += 1
						self.handler.answerEnq(self.slotid, answer)
						self.showWait()
						break
					else:
						self.is_pin_list = 0
						self.addEntry(list, entry)
				else:
					if entry[0] == "TITLE":
						self["title"].setText(entry[1])
					elif entry[0] == "SUBTITLE":
						self["subtitle"].setText(entry[1])
					elif entry[0] == "BOTTOM":
						self["bottom"].setText(entry[1])
					elif entry[0] == "TEXT":
						self.addEntry(list, entry)
			self.updateList(list)

	def ciStateChanged(self):
		do_close = False
		if self.action == 0:			# reset
			do_close = True
		if self.action == 1:			# init
			do_close = True

		# module still there ?
		if self.handler.getState(self.slotid) != 2:
			do_close = True

		# mmi session still active ?
		if self.handler.getMMIState(self.slotid) != 1:
			do_close = True

		if do_close:
			self.closeMmi()
		elif self.action > 1 and self.handler.availableMMI(self.slotid) == 1:
			self.showScreen()

		# FIXME: check for mmi-session closed


class CiMessageHandler:
	def __init__(self):
		self.session = None
		self.auto_close = False
		self.ci = {}
		self.dlgs = {}
		eDVBCI_UI.getInstance().ciStateChanged.get().append(self.ciStateChanged)

	def setSession(self, session):
		self.session = session

	def ciStateChanged(self, slot):
		if slot in self.ci:
			self.ci[slot](slot)
		else:
			handler = eDVBCI_UI.getInstance()
			if slot in self.dlgs:
				self.dlgs[slot].ciStateChanged()
			elif handler.availableMMI(slot) == 1:
				if self.session:
					show_ui = False
					if config.ci[slot].show_ci_messages.value:
						show_ui = True
					screen_data = handler.getMMIScreen(slot)
					if config.ci[slot].use_static_pin.value:
						if screen_data is not None and len(screen_data):
							ci_tag = screen_data[0][0]
							if ci_tag == 'ENQ' and len(screen_data) >= 2 and screen_data[1][0] == 'PIN':
								if str(config.ci[slot].static_pin.value) == "0":
									show_ui = True
								else:
									answer = str(config.ci[slot].static_pin.value)
									length = len(answer)
									while length < config.ci[slot].static_pin.getLength():
										answer = '0' + answer
										length += 1
									handler.answerEnq(slot, answer)
									show_ui = False
									self.auto_close = True
							elif ci_tag == 'CLOSE' and self.auto_close:
								show_ui = False
								self.auto_close = False
					if show_ui and not forceNotShowCiMessages and not Screens.Standby.inStandby and not config.misc.firstrun.value:
						try:
							self.dlgs[slot] = self.session.openWithCallback(self.dlgClosed, MMIDialog, slot, 3, screen_data=screen_data)
						except Exception:
							pass

	def dlgClosed(self, slot):
		if slot in self.dlgs:
			del self.dlgs[slot]

	def registerCIMessageHandler(self, slot, func):
		self.unregisterCIMessageHandler(slot)
		self.ci[slot] = func

	def unregisterCIMessageHandler(self, slot):
		if slot in self.ci:
			del self.ci[slot]


CiHandler = CiMessageHandler()


class CiSelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("Common Interface"))
		self["actions"] = ActionMap(["OkCancelActions", "CiSelectionActions", "ColorActions"],
			{
				"left": self.keyLeft,
				"right": self.keyRight,
				"ok": self.okbuttonClick,
				"cancel": self.cancel,
				"red": self.cancel
			}, -1)

		self.dlg = None
		self.state = {}
		self.ciplushelper = config.cimisc.cihelperenabled.value and BoxInfo.getItem("CIPlusHelper") and BoxInfo.getItem("CommonInterface")
		self.list = []
		self.slot = 0
		for slot in range(BoxInfo.getItem("CommonInterface")):
			state = eDVBCI_UI.getInstance().getState(slot)
			if state != -1:
				self.slot += 1
				self.appendEntries(slot, state)
				CiHandler.registerCIMessageHandler(slot, self.ciStateChanged)

		menuList = ConfigList(self.list)
		menuList.list = self.list
		menuList.l.setList(self.list)
		self["entries"] = menuList
		self["entries"].onSelectionChanged.append(self.selectionChanged)
		self["text"] = Label("")
		self["key_red"] = StaticText(_("Exit"))
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		global forceNotShowCiMessages
		forceNotShowCiMessages = False
		cur = self["entries"].getCurrent()
		if cur and len(cur) > 2:
			self["text"].setText(_("Slot %d") % (cur[3] + 1))
		elif not cur:
			self["text"].setText(_("no module found"))

	def selectionChanged(self):
		if self.slot > 1:
			cur = self["entries"].getCurrent()
			if cur and len(cur) > 2:
				self["text"].setText(cur[0] == "**************************" and " " or cur[0] == _("DVB CI Delay") and _("All slots") or cur[0] == _("CI Boot Delay") and _("All slots") or _("Slot %d") % (cur[3] + 1))

	def keyConfigEntry(self, key):
		try:
			self["entries"].handleKey(key)
			self["entries"].getCurrent()[1].save()
		except:
			pass

	def keyLeft(self):
		self.keyConfigEntry(KEY_LEFT)

	def keyRight(self):
		self.keyConfigEntry(KEY_RIGHT)

	def appendEntries(self, slot, state):
		self.state[slot] = state
		if self.slot > 1:
			self.list.append(("**************************", ConfigNothing(), 3, slot))
		self.list.append((_("CI enabled"), config.ci[slot].enabled, -1, slot))
		if self.state[slot] in (0, 3) or not config.ci[slot].enabled.value:
			self.list.append(((not config.ci[slot].enabled.value or self.state[slot] == 3) and _("module disabled") or _("no module found"), ConfigNothing(), 2, slot))
			return
		if not self.ciplushelper:
			self.list.append((_("Reset"), ConfigNothing(), _("Press OK to reset module"), 0, slot))
			self.list.append((_("Init"), ConfigNothing(), _("Press OK to init module"), 1, slot))

		if self.state[slot] == 1:  # module in init
			self.list.append((_("init module"), ConfigNothing(), 2, slot))
		elif self.state[slot] == 2:  # module ready
			appname = eDVBCI_UI.getInstance().getAppName(slot)
			self.list.append((appname, ConfigNothing(), 2, slot))

		self.list.append((_("Set persistent PIN code"), config.ci[slot].use_static_pin, 3, slot))
		self.list.append((_("Enter persistent PIN code"), ConfigNothing(), 5, slot))
		self.list.append((_("Reset persistent PIN code"), ConfigNothing(), 6, slot))
		self.list.append((_("Show CI messages"), config.ci[slot].show_ci_messages, 3, slot))
		self.list.append((_("Disable operator profiles"), config.ci[slot].disable_operator_profile))
		self.list.append((_("Descrambling options") + " *", config.ci[slot].alternative_ca_handling))
		self.list.append((_("Multiple service support"), config.ci[slot].canDescrambleMultipleServices, 3, slot))
		if BoxInfo.getItem("CI%dSupportsHighBitrates" % slot):
			self.list.append((_("High bitrate support"), config.ci[slot].highBitrate, 3, slot))
		if BoxInfo.getItem("CI%dRelevantPidsRoutingSupport" % slot):
			self.list.append((_("PID Filtering"), config.ci[slot].relevantPidsRouting, 3, slot))
		if BoxInfo.getItem("CommonInterfaceCIDelay"):
			self.list.append((_("DVB CI Delay"), config.cimisc.dvbCiDelay, 3, slot))
		self.list.append((_("CI Boot Delay"), config.cimisc.bootDelay, 3, slot))
		self.list.append((_("CI+ Helper"), config.cimisc.cihelperenabled, 3, slot))

	def updateState(self, slot):
		self.list = []
		self.slot = 0
		for module in range(BoxInfo.getItem("CommonInterface")):
			state = eDVBCI_UI.getInstance().getState(module)
			if state != -1:
				self.slot += 1
				self.appendEntries(module, state)
		lst = self["entries"]
		lst.list = self.list
		lst.l.setList(self.list)

	def ciStateChanged(self, slot):
		if self.dlg:
			self.dlg.ciStateChanged()
		else:
			state = eDVBCI_UI.getInstance().getState(slot)
			if self.state[slot] != state:
				self.state[slot] = state
				self.updateState(slot)

	def dlgClosed(self, slot):
		self.dlg = None

	def okbuttonClick(self):
		cur = self["entries"].getCurrent()
		if cur and len(cur) > 2:
			action = cur[2]
			slot = cur[3]
			if action < 0 or action == 3:
				if isinstance(cur[1], ConfigBoolean):
					self.keyRight()
				elif isinstance(cur[1], ConfigSelection):
					self.keySelection()
			elif action == 0: #reset
				eDVBCI_UI.getInstance().setReset(slot)
				authFile = f"/etc/ciplus/ci_auth_slot_{slot}.bin"
				if exists(authFile):
					remove(authFile)
			elif action == 1:  # init
				eDVBCI_UI.getInstance().setInit(slot)
			elif action == 5:
				self.session.openWithCallback(self.cancelCB, PermanentPinEntry, config.ci[slot].static_pin, _("Smartcard PIN"))
			elif action == 6:
				config.ci[slot].static_pin.value = 0
				config.ci[slot].static_pin.save()
				self.session.openWithCallback(self.cancelCB, MessageBox, _("The saved PIN was cleared."), MessageBox.TYPE_INFO)
			elif action == 2 and self.state[slot] == 2:
				self.dlg = self.session.openWithCallback(self.dlgClosed, MMIDialog, slot, action)

	def keySelection(self):
		currConfig = self["entries"].getCurrent()
		if currConfig and len(currConfig[1].choices.choices) > 1:
			self.session.openWithCallback(
				self.keySelectionCallback, ChoiceBox, title=currConfig[0],
				list=list(zip(currConfig[1].description, currConfig[1].choices)),
				selection=currConfig[1].getIndex(),
				keys=[]
			)

	def keySelectionCallback(self, answer):
		if answer:
			self["entries"].getCurrent()[1].value = answer[1]

	def cancelCB(self, value):
		pass

	def cancel(self):
		for slot in range(BoxInfo.getItem("CommonInterface")):
			state = eDVBCI_UI.getInstance().getState(slot)
			if state != -1:
				CiHandler.unregisterCIMessageHandler(slot)
		self.close()


class PermanentPinEntry(ConfigListScreen, Screen):
	def __init__(self, session, pin, pin_slot):
		Screen.__init__(self, session)
		self.skinName = ["ParentalControlChangePin", "Setup"]
		self.setTitle(_("Enter PIN code"))
		self.onChangedEntry = []

		self.slot = pin_slot
		self.pin = pin
		self.list = []
		self.pin1 = ConfigPIN(default=0, censor="*")
		self.pin2 = ConfigPIN(default=0, censor="*")
		self.pin1.addEndNotifier(boundFunction(self.valueChanged, 1))
		self.pin2.addEndNotifier(boundFunction(self.valueChanged, 2))
		self.list.append((_("Enter PIN"), NoSave(self.pin1)))
		self.list.append((_("Reenter PIN"), NoSave(self.pin2)))
		ConfigListScreen.__init__(self, self.list, fullUI=True)

	def valueChanged(self, pin, value):
		if pin == 1:
			self["config"].setCurrentIndex(1)
		elif pin == 2:
			self.keyOK()

	def keySave(self):
		if self.pin1.value == self.pin2.value:
			self.pin.value = self.pin1.value
			self.pin.save()
			self.session.openWithCallback(self.close, MessageBox, _("The PIN code has been saved successfully."), MessageBox.TYPE_INFO)
		else:
			self.session.open(MessageBox, _("The PIN codes you entered are different."), MessageBox.TYPE_ERROR)

	def keyCancel(self):
		self.close(None)
