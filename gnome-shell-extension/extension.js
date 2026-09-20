import Gio from 'gi://Gio';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'org.izzet.QuotaBubble';
const OBJECT_PATH = '/org/izzet/QuotaBubble';
const INTERFACE_NAME = 'org.izzet.QuotaBubble1';

export default class QuotaBubbleExtension extends Extension {
    enable() {
        this._label = new St.Label({
            style_class: 'quotabubble',
            text: 'QuotaBubble\nLoading…',
        });
        Main.layoutManager.addChrome(this._label, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._label.set_position(24, 24);
        this._connectService();
    }

    disable() {
        this._proxy?.disconnectSignal(this._signalId);
        this._proxy = null;
        this._label?.destroy();
        this._label = null;
    }

    async _connectService() {
        try {
            this._proxy = await Gio.DBusProxy.new_for_bus(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                null,
                BUS_NAME,
                OBJECT_PATH,
                INTERFACE_NAME,
                null,
            );
            this._signalId = this._proxy.connectSignal(
                'StateChanged',
                (_proxy, _sender, _name, parameters) => this._render(parameters.deepUnpack()[0]),
            );
            const result = await this._proxy.call(
                'GetState',
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
            );
            this._render(result.deepUnpack()[0]);
        } catch (error) {
            console.error(`QuotaBubble could not connect to its service: ${error.message}`);
            this._label?.set_text('QuotaBubble\nService unavailable');
        }
    }

    _render(payload) {
        const state = JSON.parse(payload);
        const rows = state.snapshots.map(snapshot => {
            if (snapshot.status !== 'ok')
                return `${snapshot.display_name}  ${snapshot.message ?? snapshot.status}`;
            const window = snapshot.windows[0];
            return window ? `${snapshot.display_name}  ${Math.round(window.used_pct)}%` : snapshot.display_name;
        });
        this._label?.set_text(rows.length ? rows.join('\n') : 'QuotaBubble\nNo providers');
    }
}
