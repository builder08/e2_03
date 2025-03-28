# -*- coding: utf-8 -*-
from Screens.Screen import Screen
from Components.Pixmap import Pixmap
from Components.config import config, ConfigInteger
from Components.Sources.Boolean import Boolean
from Components.Label import Label
from Components.ServiceEventTracker import ServiceEventTracker
from enigma import eDVBSatelliteEquipmentControl, eTimer, iPlayableService, eServiceCenter, iServiceInformation
from Components.NimManager import nimmanager
from Components.SystemInfo import BoxInfo
from Components.Sources.FrontendStatus import FrontendStatus

INVALID_POSITION = 9999
config.misc.lastrotorposition = ConfigInteger(INVALID_POSITION)


class Dish(Screen):
	STATE_HIDDEN = 0
	STATE_SHOWN = 1
	skin = """
		<screen name="Dish" flags="wfNoBorder" position="86,100" size="130,220" title="Dish" zPosition="1" backgroundColor="#11396D" >
			<widget name="Dishpixmap" position="0,0"  size="130,160" zPosition="-1" pixmap="icons/dish.png" transparent="1" alphaTest="on" />
			<widget name="turnTime"   position="5,0"   size="120,20" zPosition="1" font="Regular;20" horizontalAlignment="right" shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="From"       position="5,162" size="50,17" zPosition="1" font="Regular;17" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1"  />
			<widget name="posFrom"    position="57,160" size="70,20" zPosition="1" font="Regular;20" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="Goto"       position="5,182"  size="50,17" zPosition="1" font="Regular;17" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget name="posGoto"    position="57,180" size="70,20" zPosition="1" font="Regular;20" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="tunerName"  position="5,144"  size="90,16" zPosition="2" font="Regular;14" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget name="turnSpeed"  position="75,95" size="50,16" zPosition="2" font="Regular;14" horizontalAlignment="right" shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget source="session.FrontendStatus" render="Progress" position="5,205" size="120,10" pixmap="bar_snr.png" zPosition="2" borderWidth="2" borderColor="#cccccc">
				<convert type="FrontendInfo">SNR</convert>
			</widget>
		</screen>"""

	def __init__(self, session):
		self.skin = Dish.skin
		Screen.__init__(self, session)
		self["Dishpixmap"] = Pixmap()
		self["turnTime"] = Label("")
		self["posFrom"] = Label("")
		self["posGoto"] = Label("")
		self["From"] = Label(_("From:"))
		self["Goto"] = Label(_("Goto:"))
		self["tunerName"] = Label("")
		self["turnSpeed"] = Label("")
		self.updateRotorSatList()
		self.rotorTimer = eTimer()
		self.rotorTimer.callback.append(self.updateRotorMovingState)
		self.turnTimer = eTimer()
		self.turnTimer.callback.append(self.turnTimerLoop)
		self.timeoutTimer = eTimer()
		self.timeoutTimer.callback.append(self.testIsTuned)
		config.usage.showdish.addNotifier(self.configChanged)
		self.rotor_pos = self.cur_orbpos = config.misc.lastrotorposition.value
		self.tuner = self.turn_time = self.total_time = self.pmt_timeout = self.close_timeout = self.rotor_sat = None
		self.cur_polar = 0
		self.__state = self.STATE_HIDDEN
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)
		from Screens.InfoBarGenerics import streamrelay
		self.streamrelay = streamrelay
		self.__event_tracker = ServiceEventTracker(screen=self,
			eventmap={
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evTunedIn: self.__serviceTunedIn,
			})

	def updateRotorSatList(self):
		self.available_sat = []
		for x in nimmanager.nim_slots:
			for sat in nimmanager.getRotorSatListForNim(x.slot):
				if sat[0] not in self.available_sat:
					self.available_sat.append(sat[0])

	def getRotorMovingState(self):
		return eDVBSatelliteEquipmentControl.getInstance().isRotorMoving()

	def updateRotorMovingState(self):
		moving = self.getRotorMovingState()
		if moving:
			if self.rotor_sat is None:
				self.rotor_sat = self.isSatRotorMode()
			if self.rotor_sat:
				if self.cur_orbpos != INVALID_POSITION and self.cur_orbpos != config.misc.lastrotorposition.value:
					config.misc.lastrotorposition.value = self.cur_orbpos
					config.misc.lastrotorposition.save()
				if self.__state == self.STATE_HIDDEN:
					self.show()
			else:
				self.__toHide()

	def turnTimerLoop(self):
		if self.total_time:
			self.turn_time -= 1
			self["turnTime"].setText(self.FormatTurnTime(self.turn_time))
			self.close_timeout -= 1
			if self.close_timeout < 0:
				print("[Dish] timeout!")
				self.__toHide()
		elif self.streamrelay.checkService(self.session.nav.getCurrentlyPlayingServiceReference()) and not self.getRotorMovingState():
			self.__toHide()

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		prev_rotor_pos = self.rotor_pos
		if self.tuner is not None:
			for x in nimmanager.nim_slots:
				if x.slot == self.tuner:
					rotorposition = hasattr(x.config, 'lastsatrotorposition') and x.config.lastsatrotorposition.value or ""
					if rotorposition.isdigit():
						prev_rotor_pos = int(rotorposition)
					break
		self.rotor_pos = self.cur_orbpos
		self.total_time = self.getTurnTime(prev_rotor_pos, self.rotor_pos, self.cur_polar)
		self.turn_time = self.total_time
		self.close_timeout = round(self.total_time * 1.25) # aded 25%
		self["posFrom"].setText(self.OrbToStr(prev_rotor_pos))
		self["posGoto"].setText(self.OrbToStr(self.rotor_pos))
		self["tunerName"].setText(self.getTunerName())
		if self.total_time == 0:
			self["turnTime"].setText("")
			self["turnSpeed"].setText("")
		else:
			self["turnTime"].setText(self.FormatTurnTime(self.turn_time))
			self["turnSpeed"].setText(str(self.getTurningSpeed(self.cur_polar)) + chr(176) + _("/s"))
		self.turnTimer.start(1000, False)

	def __onHide(self):
		self.__state = self.STATE_HIDDEN
		self.turnTimer.stop()
		self.updateRotorSatList()

	def __serviceStarted(self):
		if self.__state == self.STATE_SHOWN:
			self.hide()
		if BoxInfo.getItem("isRotorTuner") and self.showdish:
			service = self.session.nav.getCurrentService()
			info = service and service.info()
			data = info and info.getInfoObject(iServiceInformation.sTransponderData)
			if not data or data == -1:
				return
			tuner_type = data.get("tuner_type")
			if tuner_type and "DVB-S" in tuner_type:
				cur_orbpos = data.get("orbital_position", INVALID_POSITION)
				if cur_orbpos in self.available_sat:
					self.cur_orbpos = cur_orbpos
					self.cur_polar = data.get("polarization", 0)
					self.rotorTimer.start(500, False)

	def __toHide(self):
		self.rotorTimer.stop()
		self.timeoutTimer.stop()
		self.tuner = self.rotor_sat = None
		if self.__state == self.STATE_SHOWN:
			self.hide()

	def __serviceTunedIn(self):
		if self.close_timeout is not None and not self.streamrelay.checkService(self.session.nav.getCurrentlyPlayingServiceReference()):
			self.pmt_timeout = self.close_timeout
			self.timeoutTimer.start(500, False)

	def testIsTuned(self):
		if self.pmt_timeout >= 0:
			service = self.session.nav.getCurrentService()
			info = service and service.info()
			pmt = info and info.getInfo(iServiceInformation.sPMTPID) or -1
			if pmt >= 0:
				print("[Dish] tuned, closing...")
				self.__toHide()
			else:
				self.pmt_timeout -= 0.5
		else:
			self.__toHide()
			print("[Dish] tuning failed")

	def dishState(self):
		return self.__state

	def configChanged(self, configElement):
		self.showdish = configElement.value

	def getTurnTime(self, start, end, pol=0):
		mrt = abs(start - end) if start and end else 0
		if mrt > 0:
			if mrt > 1800:
				mrt = 3600 - mrt
			if mrt % 10:
				mrt += 10
			mrt = round((mrt * 1000 / self.getTurningSpeed(pol)) / 10000) + 3
		return mrt

	def isSatRotorMode(self):
		satRotorMode = False
		self.tuner = self.getCurrentTuner()
		if self.tuner is not None:
			for sat in nimmanager.getRotorSatListForNim(self.tuner):
				if sat[0] == self.cur_orbpos:
					satRotorMode = True
					break
		return satRotorMode

	def getTurningSpeed(self, pol=0):
		tuner = self.getCurrentTuner()
		if tuner is not None:
			nimConfig = nimmanager.getNimConfig(tuner)
			if nimConfig.configMode.value == "simple":
				if "positioner" in nimConfig.diseqcMode.value:
					nim = config.Nims[tuner]
					if pol in (1, 3):  # vertical
						return nim.turningspeedV.float
					return nim.turningspeedH.float
			elif nimConfig.configMode.value == "advanced":
				if self.cur_orbpos != INVALID_POSITION:
					if self.cur_orbpos in nimConfig.advanced.sat.keys():
						currSat = nimConfig.advanced.sat[self.cur_orbpos]
						lnbnum = int(currSat.lnb.value)
						currLnb = lnbnum and nimConfig.advanced.lnb[lnbnum]
						diseqcmode = currLnb and currLnb.diseqcMode.value or ""
						if diseqcmode == "1_2":
							if pol in (1, 3):  # vertical
								return currLnb.turningspeedV.float
							return currLnb.turningspeedH.float
		if pol in (1, 3):
			return 1.0
		return 1.5

	def getCurrentTuner(self):
		service = self.session.nav.getCurrentService()
		feinfo = service and service.frontendInfo()
		tuner = feinfo and feinfo.getFrontendData()
		if tuner is not None:
			return tuner.get("tuner_number")
		return None

	def getTunerName(self):
		nr = self.getCurrentTuner()
		if nr is not None:
			return _("Tuner") + " " + chr(nr + 65)
		return ""

	def OrbToStr(self, orbpos):
		if orbpos == INVALID_POSITION:
			return _("N/A")
		if orbpos > 1800:
			orbpos = 3600 - orbpos
			return _("%.1f° W") % (orbpos / 10.0)
		return _("%.1f° E") % (orbpos / 10.0)

	def FormatTurnTime(self, time):
		t = abs(time)
		return "%s%02d:%02d" % (time < 0 and "- " or "", t / 60 % 60, t % 60)


class Dishpip(Dish, Screen):
	STATE_HIDDEN = 0
	STATE_SHOWN = 1
	skin = """
		<screen name="Dishpip" flags="wfNoBorder" position="86,100" size="130,220" title="DishPiP" zPosition="1" backgroundColor="#11396D" >
			<widget source="Dishpixmap" render="Pixmap" pixmap="icons/dish.png" zPosition="-1" position="0,0" size="130,160" alphaTest="on">
				<convert type="ConditionalShowHide">Blink</convert>
			</widget>
			<widget name="turnTime"   position="5,0"   size="120,20" zPosition="1" font="Regular;20" horizontalAlignment="right" shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="From"       position="5,162" size="50,17" zPosition="1" font="Regular;17" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1"  />
			<widget name="posFrom"    position="57,160" size="70,20" zPosition="1" font="Regular;20" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="Goto"       position="5,182"  size="50,17" zPosition="1" font="Regular;17" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget name="posGoto"    position="57,180" size="70,20" zPosition="1" font="Regular;20" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-2" transparent="1" />
			<widget name="tunerName"  position="5,144"  size="90,16" zPosition="2" font="Regular;14" horizontalAlignment="left"  shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget name="turnSpeed"  position="75,95" size="50,16" zPosition="2" font="Regular;14" horizontalAlignment="right" shadowColor="black" shadowOffset="-2,-1" transparent="1" />
			<widget source="Frontend" render="Progress" position="5,205" size="120,10" pixmap="bar_snr.png" zPosition="2" borderWidth="2" borderColor="#cccccc">
				<convert type="FrontendInfo">SNR</convert>
			</widget>
		</screen>"""

	def __init__(self, session):
		self.skin = Dishpip.skin
		Screen.__init__(self, session)
		self["Dishpixmap"] = Boolean(fixed=True, poll=1500)
		self["turnTime"] = Label("")
		self["posFrom"] = Label("")
		self["posGoto"] = Label("")
		self["From"] = Label(_("From:"))
		self["Goto"] = Label(_("Goto:"))
		self["Tuner"] = Label(_("Tuner :"))
		self["tunerName"] = Label("")
		self["turnSpeed"] = Label("")
		self.updateRotorSatList()
		self.frontend = None
		self["Frontend"] = FrontendStatus(service_source=lambda: self.frontend, update_interval=1000)
		self.rotorTimer = eTimer()
		self.rotorTimer.callback.append(self.updateRotorMovingState)
		self.turnTimer = eTimer()
		self.turnTimer.callback.append(self.turnTimerLoop)
		self.timeoutTimer = eTimer()
		self.timeoutTimer.callback.append(self.__toHide)
		self.rotor_pos = self.cur_orbpos = config.misc.lastrotorposition.value
		self.turn_time = self.total_time = None
		self.close_timeout = self.moving_timeout = self.cur_polar = 0
		self.__state = self.STATE_HIDDEN
		self.noSkinReload = True
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def updateRotorMovingState(self):
		moving = self.getRotorMovingState()
		if moving:
			if self.__state == self.STATE_HIDDEN:
				self.rotorTimer.stop()
				self.moving_timeout = 0
				if config.usage.showdish.value and BoxInfo.getItem("isRotorTuner"):
					self.show()
				if self.cur_orbpos != INVALID_POSITION and self.cur_orbpos != config.misc.lastrotorposition.value:
					config.misc.lastrotorposition.value = self.cur_orbpos
					config.misc.lastrotorposition.save()
		self.moving_timeout -= 1
		if not self.rotorTimer.isActive() and self.moving_timeout > 0:
			self.rotorTimer.start(1000, True)

	def turnTimerLoop(self):
		if self.total_time:
			self.turn_time -= 1
			self["turnTime"].setText(self.FormatTurnTime(self.turn_time))
			self.close_timeout -= 1
			if self.close_timeout <= 3:
				self.__toHide()
			# elif not self.getRotorMovingState():
			# self.turnTimer.stop()
			# self.timeoutTimer.start(10000, True)
		else:
			if not self.getRotorMovingState():
				self.turnTimer.stop()
				self.timeoutTimer.start(3000, True)

	def startPiPService(self, ref=None):
		if self.__state == self.STATE_SHOWN:
			self.__toHide()
		if ref and BoxInfo.getItem("isRotorTuner"):
			info = eServiceCenter.getInstance().info(ref)
			data = info and info.getInfoObject(ref, iServiceInformation.sTransponderData)
			if not data or data == -1:
				return
			tuner_type = data.get("tuner_type")
			if tuner_type and "DVB-S" in tuner_type:
				cur_orbpos = data.get("orbital_position", INVALID_POSITION)
				if cur_orbpos in self.available_sat:
					self.cur_orbpos = cur_orbpos
					self.cur_polar = data.get("polarization", 0)
					self.moving_timeout = 4
					if not self.rotorTimer.isActive():
						self.rotorTimer.start(1000, True)

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		prev_rotor_pos = self.rotor_pos
		tuner = self.getCurrentTuner()
		if tuner is not None:
			for x in nimmanager.nim_slots:
				if x.slot == tuner:
					rotorposition = hasattr(x.config, 'lastsatrotorposition') and x.config.lastsatrotorposition.value or ""
					if rotorposition.isdigit():
						prev_rotor_pos = int(rotorposition)
					break
		self.rotor_pos = self.cur_orbpos
		self.total_time = self.getTurnTime(prev_rotor_pos, self.rotor_pos, self.cur_polar)
		self.turn_time = self.total_time
		self.close_timeout = round(self.total_time * 1.25)  # aded 25%
		self["posFrom"].setText(self.OrbToStr(prev_rotor_pos))
		self["posGoto"].setText(self.OrbToStr(self.rotor_pos))
		self["tunerName"].setText(self.getTunerName())
		if self.total_time == 0:
			self["turnTime"].setText("")
			self["turnSpeed"].setText("")
		else:
			self["turnTime"].setText(self.FormatTurnTime(self.turn_time))
			self["turnSpeed"].setText(str(self.getTurningSpeed(self.cur_polar)) + chr(176) + _("/s"))
		self.turnTimer.start(1000, False)

	def __onHide(self):
		self.__state = self.STATE_HIDDEN
		self.updateRotorSatList()

	def setHide(self):
		self.__toHide()

	def __toHide(self):
		self.rotorTimer.stop()
		self.turnTimer.stop()
		self.timeoutTimer.stop()
		self.close_timeout = self.moving_timeout = 0
		self.frontend = None
		if self.__state == self.STATE_SHOWN:
			self.hide()

	def getCurrentTuner(self):
		if hasattr(self.session, 'pipshown') and self.session.pipshown:
			service = self.session.pip.pipservice
			if not service:
				return None
			self.frontend = service
			feinfo = service and service.frontendInfo()
			tuner = feinfo and feinfo.getFrontendData()
			if tuner is not None:
				return tuner.get("tuner_number")
		return None
