import { api } from "./api.js"
import "./domWidget.js";

function getNumberDefaults(inputData, defaultStep, precision, enable_rounding) {
	let defaultVal = inputData[1]["default"];
	let { min, max, step, round} = inputData[1];

	if (defaultVal == undefined) defaultVal = 0;
	if (min == undefined) min = 0;
	if (max == undefined) max = 2048;
	if (step == undefined) step = defaultStep;
	// precision is the number of decimal places to show.
	// by default, display the the smallest number of decimal places such that changes of size step are visible.
	if (precision == undefined) {
		precision = Math.max(-Math.floor(Math.log10(step)),0);
	}

	if (enable_rounding && (round == undefined || round === true)) {
		// by default, round the value to those decimal places shown.
		round = Math.round(1000000*Math.pow(0.1,precision))/1000000;
	}

	return { val: defaultVal, config: { min, max, step: 10.0 * step, round, precision } };
}

export function addValueControlWidget(node, targetWidget, defaultValue = "randomize", values, widgetName, inputData) {
	let name = inputData[1]?.control_after_generate;
	if(typeof name !== "string") {
		name = widgetName;
	}
	const widgets = addValueControlWidgets(node, targetWidget, defaultValue, {
		addFilterList: false,
		controlAfterGenerateName: name
	}, inputData);
	return widgets[0];
}

export function addValueControlWidgets(node, targetWidget, defaultValue = "randomize", options, inputData) {
	if (!defaultValue) defaultValue = "randomize";
	if (!options) options = {};

	const getName = (defaultName, optionName) => {
		let name = defaultName;
		if (options[optionName]) {
			name = options[optionName];
		} else if (typeof inputData?.[1]?.[defaultName] === "string") {
			name = inputData?.[1]?.[defaultName];
		} else if (inputData?.[1]?.control_prefix) {
			name = inputData?.[1]?.control_prefix + " " + name
		}
		return name;
	}

	const widgets = [];
	const valueControl = node.addWidget(
		"combo",
		getName("control_after_generate", "controlAfterGenerateName"),
		defaultValue,
		function () {},
		{
			values: ["fixed", "increment", "decrement", "randomize"],
			serialize: false, // Don't include this in prompt.
		}
	);
	widgets.push(valueControl);

	const isCombo = targetWidget.type === "combo";
	let comboFilter;
	if (isCombo && options.addFilterList !== false) {
		comboFilter = node.addWidget(
			"string",
			getName("control_filter_list", "controlFilterListName"),
			"",
			function () {},
			{
				serialize: false, // Don't include this in prompt.
			}
		);
		widgets.push(comboFilter);
	}

	valueControl.afterQueued = () => {
		var v = valueControl.value;

		if (isCombo && v !== "fixed") {
			let values = targetWidget.options.values;
			const filter = comboFilter?.value;
			if (filter) {
				let check;
				if (filter.startsWith("/") && filter.endsWith("/")) {
					try {
						const regex = new RegExp(filter.substring(1, filter.length - 1));
						check = (item) => regex.test(item);
					} catch (error) {
						console.error("Error constructing RegExp filter for node " + node.id, filter, error);
					}
				}
				if (!check) {
					const lower = filter.toLocaleLowerCase();
					check = (item) => item.toLocaleLowerCase().includes(lower);
				}
				values = values.filter(item => check(item));
				if (!values.length && targetWidget.options.values.length) {
					console.warn("Filter for node " + node.id + " has filtered out all items", filter);
				}
			}
			let current_index = values.indexOf(targetWidget.value);
			let current_length = values.length;

			switch (v) {
				case "increment":
					current_index += 1;
					break;
				case "decrement":
					current_index -= 1;
					break;
				case "randomize":
					current_index = Math.floor(Math.random() * current_length);
				default:
					break;
			}
			current_index = Math.max(0, current_index);
			current_index = Math.min(current_length - 1, current_index);
			if (current_index >= 0) {
				let value = values[current_index];
				targetWidget.value = value;
				targetWidget.callback(value);
			}
		} else {
			//number
			let min = targetWidget.options.min;
			let max = targetWidget.options.max;
			// limit to something that javascript can handle
			max = Math.min(1125899906842624, max);
			min = Math.max(-1125899906842624, min);
			let range = (max - min) / (targetWidget.options.step / 10);

			//adjust values based on valueControl Behaviour
			switch (v) {
				case "fixed":
					break;
				case "increment":
					targetWidget.value += targetWidget.options.step / 10;
					break;
				case "decrement":
					targetWidget.value -= targetWidget.options.step / 10;
					break;
				case "randomize":
					targetWidget.value = Math.floor(Math.random() * range) * (targetWidget.options.step / 10) + min;
				default:
					break;
			}
			/*check if values are over or under their respective
			 * ranges and set them to min or max.*/
			if (targetWidget.value < min) targetWidget.value = min;

			if (targetWidget.value > max)
				targetWidget.value = max;
			targetWidget.callback(targetWidget.value);
		}
	};
	return widgets;
};

function seedWidget(node, inputName, inputData, app, widgetName) {
	const seed = createIntWidget(node, inputName, inputData, app, true);
	const seedControl = addValueControlWidget(node, seed.widget, "randomize", undefined, widgetName, inputData);

	seed.widget.linkedWidgets = [seedControl];
	return seed;
}

function createIntWidget(node, inputName, inputData, app, isSeedInput) {
	const control = inputData[1]?.control_after_generate;
	if (!isSeedInput && control) {
		return seedWidget(node, inputName, inputData, app, typeof control === "string" ? control : undefined);
	}

	let widgetType = isSlider(inputData[1]["display"], app);
	const { val, config } = getNumberDefaults(inputData, 1, 0, true);
	Object.assign(config, { precision: 0 });
	return {
		widget: node.addWidget(
			widgetType,
			inputName,
			val,
			function (v) {
				const s = this.options.step / 10;
				this.value = Math.round(v / s) * s;
			},
			config
		),
	};
}

function isSlider(display, app) {
	if (app.ui.settings.getSettingValue("DCC.DisableSliders")) {
		return "number"
	}

	return (display==="slider") ? "slider" : "number"
}

function STRING(node, name, defaultVal, callback, app) {
	let res = { widget: node.addWidget("text", name, defaultVal, callback, {}) };
	return res;
}

function COMBO(node, name, enumData, callback, app) {
	let defaultValue = enumData[0];
	return { widget: node.addWidget("combo", name, defaultValue, callback, { values: enumData }) };
}

function FILEUPLOAD(node, name, filename, callback, app) {
	let uploadWidget;
	let fileWidget;
	fileWidget = node.addWidget("text", name, filename, () => {}, {})
	fileWidget.serialize = false;

	function showData(name) {
		console.log("showData called");
	}

	var default_value = fileWidget.value;
	Object.defineProperty(fileWidget, "value", {
		set : function(value) {
			this._real_value = value;
		},

		get : function() {
			let value = "";
			if (this._real_value) {
				value = this._real_value;
			} else {
				return default_value;
			}

			return value;
		}
	});

	// Add our own callback to the combo widget to render an image when it changes
	const cb = node.callback;
	fileWidget.callback = function () {
		showData(fileWidget.value);
		if (cb) {
			return cb.apply(this, arguments);
		}
	};

	// On load if we have a value then render the image
	// The value isnt set immediately so we need to wait a moment
	// No change callbacks seem to be fired on initial setting of the value
	requestAnimationFrame(() => {
		if (fileWidget.value) {
			showData(fileWidget.value);
		}
	});

	async function uploadFile(file, updateNode) {
		try {
			// Wrap file in formdata so it includes filename
			const body = new FormData();
			body.append('assetId', session.assetId);
			body.append('variantId', session.variantId);
			body.append('attributeId', element.name);
			body.append('file', file);
			const resp = await api.fetchApi("/upload", {
				method: "PUT",
				body,
			});
			if (resp.status === 200) {
				const data = await resp.json();
				// Add the file to the dropdown list and update the widget value
				if (updateNode) {
					showData(path);
					fileWidget.value = data.name;
				}
			} else {
				alert(resp.status + " - " + resp.statusText);
			}
		} catch (error) {
			alert(error);
		}
	}

	const fileInput = document.createElement("input");
	Object.assign(fileInput, {
		type: "file",
		accept: "application/zip",
		style: "display: none",
		onchange: async () => {
			if (fileInput.files.length) {
				await uploadFile(fileInput.files[0], true);
			}
		},
	});
	document.body.append(fileInput);

	// Create the button widget for selecting the files
	uploadWidget = node.addWidget("button", "choose file to upload", "datafile", () => {
		fileInput.click();
	});
	uploadWidget.serialize = false;

	// Add handler to check if an image is being dragged over our node
	node.onDragOver = function (e) {
		if (e.dataTransfer && e.dataTransfer.items) {
			const datafile = [...e.dataTransfer.items].find((f) => f.kind === "file");
			return !!datafile;
		}

		return false;
	};

	// On drop upload files
	node.onDragDrop = function (e) {
		console.log("onDragDrop called");
		let handled = false;
		for (const file of e.dataTransfer.files) {
			if (file.type.endsWith("zip")) {
				uploadFile(file, !handled); // Dont await these, any order is fine, only update on first one
				handled = true;
			}
		}

		return handled;
	};

	node.pasteFile = function(file) {
		if (file.type.endsWith("zip")) {
			uploadFile(file, true);
			return true;
		}
		return false;
	}

	return { widgets: [fileWidget, uploadWidget] };
}

export const DCCWidgets = {
	"OUTPUT_ATTR_NAME": STRING,
	"DATATYPE": COMBO,
	"DATAFILE": FILEUPLOAD,
	"STRING": STRING
};
