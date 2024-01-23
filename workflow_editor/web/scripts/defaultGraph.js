export const defaultGraph = {
	last_node_id: 9,
	last_link_id: 9,
	nodes: [
		{
			id: 8,
			type: "Pdf2Img",
			pos: [707, 303],
			size: { 0: 210, 1: 46 },
			flags: {},
			order: 0,
			mode: 0,
			inputs: [
						{
							name: "input_pdf",
							type: "PDF",
							link: null
						}
					],
			outputs: [
						{
							name: "output_imgs",
							type: "IMAGE",
							links: [9],
							slot_index: 0
						}
					],
			properties: {
				"Node name for S&R": "VAEDecode"
			}
		},
		{
			id: 9,
			type: "ImageCaptioning",
			pos: [1177, 288],
			size: { 0: 210, 1: 58 },
			flags: {},
			order: 1,
			mode: 0,
			inputs: [
						{
							name: "input_img",
							type: "IMAGE",
							link: 9
						}
					],
			outputs: [
						{
							name: "output_caption",
							type: "JSON",
							links: [9],
							slot_index: 0
						}
					],
			properties: {},
		}
	],
	links: [
		[9, 8, 0, 9, 0, "IMAGE"],
	],
	groups: [],
	config: {},
	extra: {},
	version: 0.4,
};
