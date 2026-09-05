import os
import sys
import re

sys.path.append(os.path.dirname(__file__))
from qc_engine import audit_chapter
from glossary_engine import load_glossary, save_glossary

CHAPTER_1_RAW_P_COUNT = 68
CHAPTER_2_RAW_P_COUNT = 60
CHAPTER_3_RAW_P_COUNT = 54
CHAPTER_4_RAW_P_COUNT = 61
CHAPTER_5_RAW_P_COUNT = 58

chap_1_p = [
    "Chương 1 là ác mộng vẫn là biết trước?",
    "“Đừng tới đây! Bảo vệ tốt cho ba mẹ!”",
    "“Khương Biết Nguyên! Đừng mà!”",
    "Khương Tri Uẩn đột nhiên từ trong cơn mộng mị bừng tỉnh giật mình ngồi dậy. Mồ hôi lạnh trên trán rơi xuống từng giọt lớn, nhanh chóng loang ra thành một mảng trên chiếc chăn điều hòa màu vàng ấm áp. Cô ngơ ngác nhìn quanh bốn phía, em trai và ba mẹ đều không có ở đây, cô vẫn đang nằm yên lành trên chiếc giường đơn trong căn hộ ở thành phố C.",
    "Tất cả chỉ là một giấc mơ thôi sao?",
    "Nhưng tại sao nó lại chân thực đến thế?",
    "Trong giấc mơ, cô thấy ở Hoa Quốc sắp bùng phát một loại virus nguy hiểm. Những kẻ bị nhiễm điên cuồng khát máu, thấy người là lao vào cắn xé. Mà thành phố C nơi cô đang sống lại chính là điểm bùng phát dịch bệnh đầu tiên.",
    "Sau khi virus xuất hiện, cô hoàn toàn mất liên lạc với cha mẹ và em trai ở thành phố B. Toàn bộ hệ thống phương tiện giao thông công cộng trên cả nước đều bị tê liệt. Em trai Khương Biết Nguyên vì lo lắng đi tìm cô nên đã quyết định tự mình lái xe đến thành phố C.",
    "Kết quả, vừa mới ra khỏi thành phố B, em ấy đã bị đám người nhiễm virus vây công. Còn chưa kịp chờ cứu viện tới, em trai đã bị kẻ lây nhiễm cắn chết ngay trong xe. Tư thế chết vô cùng thảm khốc, mà trước khi trút hơi thở cuối cùng, em ấy vẫn cố gắng gọi điện thoại cho cô để xác nhận xem cô có an toàn hay không.",
    "Dù chỉ là một giấc mơ, nhưng cảm giác đó quá mức chân thực. Cô dường như vẫn còn cảm nhận được dòng máu ấm áp của em trai và gương mặt dữ tợn của kẻ nhiễm virus.",
    "Khương Tri Uẩn xoay người lấy chiếc điện thoại trên tủ đầu giường, lập tức bấm số gọi cho em trai.",
    "“Chị, mới mấy giờ sáng rồi, chị làm gì thế?”",
    "Nghe giọng nói trầm thấp còn ngái ngủ của em trai Khương Biết Nguyên vang lên qua điện thoại, trái tim đang treo lơ lửng của Khương Tri Uẩn mới rốt cuộc trở lại lồng ngực. Cô liếc nhìn màn hình điện thoại: đúng ba giờ sáng.",
    "Trách cô quan tâm quá hóa loạn, bị giấc ác mộng dọa sợ đến khiếp vía, chỉ muốn lập tức xác định xem người nhà có an toàn hay không.",
    "“Không có gì, chị chỉ muốn kiểm tra đột xuất xem em có thức đêm chơi game không thôi.”",
    "“Chị đùa em đấy à?” Khương Biết Nguyên cạn lời.",
    "“Ba mẹ có khỏe không?”",
    "“Ba mẹ đang ngủ ở dưới lầu đấy. Chị sao thế chị?” Nửa đêm nửa hôm gọi điện hỏi mấy chuyện lặt vặt không đâu, Khương Biết Nguyên cảm thấy chị gái mình hôm nay có chút kỳ lạ.",
    "“Chị thì làm sao được chứ, chỉ là quan tâm mọi người chút thôi. Được rồi, chị ngủ đây.” Sợ Khương Biết Nguyên truy hỏi tiếp, Khương Tri Uẩn vội vàng nói vài câu rồi cúp máy.",
    "“Tút tút tút...”",
    "Khương Biết Nguyên còn chưa kịp nói thêm câu nào thì điện thoại đã bị ngắt kết nối. Nhìn màn hình tối đen, cậu càng nghĩ lại càng thấy không yên tâm. Cậu định ngồi dậy xuống lầu nói với cha mẹ, nhưng lại nghĩ hiện tại mới ba giờ sáng nên đành nằm xuống lại. Nhớ đến hành vi bất thường của chị gái, cậu trằn trọc mãi mà không sao ngủ tiếp được.",
    "Nếu người nhà không sao, vậy vừa rồi chắc chắn chỉ là giấc mơ thôi. Có lẽ cô đã lâu không về nhà nên nhớ mọi người, ban ngày nghĩ gì đêm mơ nấy. Qua hai ngày nữa cô sẽ xếp sắp công việc về thăm nhà một chuyến. Còn về virus hay người nhiễm gì đó thì quá nhảm nhí rồi, chắc chắn là do cô đọc tiểu thuyết mạt thế quá nhiều mà ra.",
    "Sau khi tự trấn an bản thân, Khương Tri Uẩn kéo chăn lên trùm kín đầu rồi lại chìm vào giấc ngủ, hoàn toàn không biết một cuộc điện thoại của mình đã khiến Khương Biết Nguyên thao thức suốt cả đêm.",
    "Tuy rằng đêm qua ngủ không ngon giấc, nhưng sáng hôm sau, với tư cách là một dân văn phòng ngành tài chính mẫn cán, Khương Tri Uẩn vẫn đúng giờ ngồi dậy theo tiếng chuông báo thức.",
    "Vừa sửa soạn xong bước ra khỏi cửa, cô liền gặp đôi cặp đôi sống chung ở căn hộ kế bên cũng chuẩn bị đi làm.",
    "Khương Tri Uẩn có ấn tượng khá tốt về cô gái nhà bên. Cô ấy tên là Trần Quyên, làm biên tập viên, tính cách rất dịu dàng. Hai người từng chào hỏi nhau vài lần, Trần Quyên còn từng giúp Khương Tri Uẩn nhận hàng chuyển phát nhanh.",
    "“Đi làm hả Tri Uẩn?” Trần Quyên chủ động lên tiếng chào hỏi.",
    "“Ừm, chúng ta cùng đi thôi.”",
    "Cả ba người cùng bước vào thang máy. Khương Tri Uẩn và Trần Quyên đồng thời đưa tay định bấm phím chuyển tầng. Đúng lúc ngón tay Khương Tri Uẩn vừa khẽ chạm vào ngón tay Trần Quyên, trong đầu cô đột nhiên xẹt qua một hình ảnh: Trần Quyên trượt chân ngã ở cầu thang bộ, ngã xoài ra đất và cất tiếng kêu rên đau đớn. Cô hoảng hốt rụt tay lại, theo bản năng lùi về sau một bước.",
    "Trần Quyên thấy Khương Tri Uẩn ngả người về phía sau thì ân cần hỏi: “Sao thế em? Bị tụt huyết áp à?”",
    "“Không có gì, không có gì đâu ạ.” Khương Tri Uẩn không biết giải thích làm sao về phản ứng kỳ lạ của mình, đành chữa thẹn: “Chắc tại em chưa ăn sáng đấy ạ.”",
    "“Này.” Trần Quyên lấy từ trong túi xách ra một thanh sô-cô-la: “Ăn tạm lót bụng trước đi.”",
    "Khương Tri Uẩn vội nhận lấy: “Cảm ơn chị nhiều nha, chị tốt quá.”",
    "Trần Quyên được khen thì hơi ngại ngùng, liền nép sát vào người bạn trai. Anh bạn trai đưa tay ôm lấy eo cô, hai người gật đầu chào tạm biệt Khương Tri Uẩn rồi bước ra khỏi thang máy trước.",
    "Nhìn bóng lưng hai người nắm tay nhau bước đi, nhớ đến hình ảnh hiện ra trong đầu khi chạm vào Trần Quyên vừa rồi, trong lòng Khương Tri Uẩn dấy lên một nỗi bất an mãnh liệt. Cô theo bản năng muốn cất tiếng gọi họ lại, nhưng điện thoại trong túi lại đột nhiên vang lên chuông báo.",
    "“Alo?”",
    "“Chị, chị dậy chưa đấy?” Là cuộc gọi từ em trai Khương Biết Nguyên.",
    "“Dậy rồi chứ sao không, hôm nay là thứ Hai mà, phải đi làm chứ.”",
    "“Đêm qua chị không gặp chuyện gì đấy chứ?”",
    "“Chị ngủ ở nhà thì gặp chuyện gì được chứ?”",
    "“Thế đêm qua nửa đêm nửa hôm chị gọi điện cho em làm gì? Làm em cứ tưởng chị bị làm sao, sợ tới mức mất ngủ cả đêm.” Khương Biết Nguyên cạn lời trước tính tình vô tư quá mức của chị gái.",
    "Nghe lời quan tâm ấm áp của em trai, Khương Tri Uẩn lại nhớ đến giấc mơ đêm qua. Nhưng đó chỉ là một giấc mơ không có căn cứ, cô chẳng biết giải thích từ đâu nên đành lấy lệ: “Chị thấy là em cày game suốt đêm thì có! Đừng tưởng nghỉ hè là muốn chơi thế nào thì chơi nhé!”",
    "Em trai Khương Biết Nguyên là sinh viên năm tư ngành Kỹ thuật Máy tính Đại học B. Sắp sửa tốt nghiệp đến nơi nên tâm trí đã sớm không còn đặt ở việc học, vừa nghỉ hè là tâm hồn đã bay đi đâu mất.",
    "“Em chơi game gì cơ chứ? Em là đang quan tâm chị đấy nhé!” Khương Biết Nguyên không ngờ chị gái lại nhân cơ hội này chỉnh mình.",
    "“Rồi rồi rồi, cảm ơn sự quan tâm của em trai nhé. Chị gái em phải đi làm đây, em tự đi ngủ bù đi.” Khương Tri Uẩnnói xong liền trực tiếp ngắt kết nối.",
    "Cuộc điện thoại này đã thành công đánh tan mối nghi ngại trong lòng Khương Tri Uẩn, khiến cô quên mất chuyện xảy ra ở thang máy vừa rồi.",
    "Vừa tới công ty, cô đồng nghiệp Lý Nhẹ Nhàng đã sán lại gần định nhiều chuyện hóng hớt. Ngay khoảnh khắc tay hai người sắp chạm vào nhau, Khương Tri Uẩn lại theo bản năng rụt tay lại.",
    "“Cậu tránh tớ làm gì thế?” Lý Nhẹ Nhàng khó hiểu.",
    "Khương Tri Uẩn cũng không hiểu bản thân làm sao nữa, đành bịa đại một lý do: “Sợ bị cậu giật điện ấy mà.”",
    "“Giữa mùa hè làm gì có tĩnh điện chứ.”",
    "“Sáng sớm ra cậu muốn nói với tớ chuyện gì thế?” Khương Tri Uẩn đánh trống lảng.",
    "“Phải rồi! Cậu ngắt lời làm tớ quên mất. Cái tên Quách Quân ở Bộ phận Sự nghiệp 2 thường xuyên quấy rầy cậu ấy, cậu còn nhớ không?”",
    "Nhắc đến tên Quách Quân này, Khương Tri Uẩn thấy ghê tởm như nuốt phải ruồi. Từ khi cô vào công ty, Quách Quân cứ như con ruồi nhặng, ba ngày hai bận mò tới đòi hẹn hò với cô. Cuối cùng cũng nhờ thấy vài lần có người đứng chờ cô dưới lầu nên hắn mới chịu yên phận.",
    "“Hắn ta làm sao? Đi tán tỉnh khách hàng rồi bị đánh à?”",
    "“Sao cậu biết hay thế! Hắn giở trò quấy rầy một nữ khách hàng, bị người ta đệ đơn khiếu nại thẳng lên trụ sở bên Mỹ luôn rồi!”",
    "“Hừ, đúng là tính nào tật nấy.”",
    "“Vừa bị sếp tổng gọi vào phòng làm việc xong, chắc chắn chuyến này bị sa thải rồi.”",
    "Khương Tri Uẩn nghe xong mà trong lòng hả hê vô cùng, đúng là ác giả ác báo.",
    "Hóng hớt xong xuôi, Khương Tri Uẩn cầm ly nước đi về phía phòng trà. Vừa lúc thấy Quách Quân đang ôm một thùng đồ đạc đi ngang qua, cô định vờ như không thấy, nhưng đối phương lại không muốn bỏ qua cho cô.",
    "Quách Quân nhìn dáng người cao ráo mảnh khảnh cùng ngũ quan tươi tắn xinh đẹp của Khương Tri Uẩn, liền quên mất chuyện trước đây cô từng nhiều lần từ chối mình, trong lòng lại rạo rực: “Tới tiễn anh đấy à?”",
    "“?” Khương Tri Uẩn thực sự chỉ muốn hất thẳng ly cà phê vào mặt hắn. Cô chẳng buồn bận tâm, xoay người định bước đi.",
    "Quách Quân liền bước tới chặn đường cô, mặt dày nói: “Nếu không phải tại anh bạn trai quân nhân kia của em đe dọa anh, Tri Uẩn à, anh sẽ không bao giờ bỏ cuộc đâu.”",
    "Bạn trai? Quân nhân? Thì ra là người nọ đã giúp cô giải quyết rắc rối Quách Quân này.",
    "“Anh mà không nhường đường thì bạn trai tôi có khi lại tới đánh cho anh một trận nữa đấy.” Khương Tri Uẩn mặt không cảm xúc đe dọa.",
    "Nhớ tới khí chất đáng sợ của người bạn trai kia, Quách Quân hậm hực lùi lại vài bước. Khương Tri Uẩn vừa định xoay người bước đi thì chợt nhớ ra điều gì, cô giơ ngón tay lên. Quách Quân tưởng cô đổi ý liền mừng thầm định tiến tới, ai ngờ Khương Tri Uẩn chỉ khẽ mở đôi môi hồng thốt ra một từ: “Cút.”",
    "Nghe thấy tiếng bước chân của đồng nghiệp đang đi tới, Quách Quân không tiện dây dưa thêm nữa, đành ôm thùng đồ xoay người rời đi.",
    "Ngay khoảnh khắc hắn xoay người, cánh tay Khương Tri Uẩn lập tức vươn về phía trước, đầu ngón tay khẽ chạm nhẹ vào tấm lưng Quách Quân. Quách Quân hoàn toàn không hay biết.",
    "Vừa xúc chạm thân thể, trong đầu cô lại hiện lên một thước phim..."
]

chap_2_p = [
    "Chương 2 thực sự có đặc dị công năng!",
    "Cô nhìn thấy Quách Quân vừa ôm thùng đồ bước ra khỏi tòa nhà văn phòng thì một toán người mặc vest đen lập tức vây vây quanh, đè Quách Quân xuống đất đánh cho một trận tơi bời.",
    "Đúng lúc đó, một chiếc xe hơi đỗ trước cửa tòa nhà bước xuống một người mỹ nữ ăn mặc tinh tế. Sau khi tát Quách Quân một cú trời giáng, nhóm người lập tức leo lên xe nghênh ngang rời đi, chỉ còn lại một mình Quách Quân nằm bò trên mặt đất rên rỉ đau đớn.",
    "Thước phim trong đầu vừa mới chiếu xong, Khương Tri Uẩn lập tức mở bừng mắt. Lúc này Quách Quân ở phía trước đã bước ra khỏi khu vực văn phòng.",
    "Khương Tri Uẩn nhẹ nhàng rón rén đi theo. Thấy Quách Quân đang đứng chờ thang máy, để kiểm chứng xem dị năng này có thật hay không, cô quay trở lại khu làm việc, nắm lấy cổ tay Lý Nhẹ Nhàng kéo đi.",
    "“Đi thôi, đi xuống lầu mua với tớ ly cà phê nào.”",
    "“Đừng kéo tớ chứ, Tri Uẩn sao cậu đi nhanh thế.” Lý Nhẹ Nhàng ngơ ngác không hiểu chuyện gì.",
    "Khương Tri Uẩn ngoái đầu nhìn cổ tay Lý Nhẹ Nhàng đang bị mình nắm chặt, nhưng trong đầu lại chẳng hiện lên bất kỳ hình ảnh nào. Chẳng lẽ vừa rồi chỉ là ảo giác sao? Mặc kệ, cứ xuống dưới xem sao đã.",
    "Hai người đi thang máy vừa xuống tới tầng trệt, Khương Tri Uẩn liền thấy Quách Quân vừa lúc bước ra khỏi cửa lớn. Đột nhiên một nhóm nam nhân mặc vest đen từ đâu lao ra, đè Quách Quân xuống mặt đất đấm đá túi bụi.",
    "“Ôi!” Lý Nhẹ Nhàng thốt lên một tiếng kinh ngạc, nắm lấy tay Khương Tri Uẩn kéo chạy ra cổng lớn xem náo nhiệt.",
    "Khương Tri Uẩn và Lý Nhẹ Nhàng đứng ở hàng đầu tiên trong đám đông, thấy rõ ràng Quách Quân bị đánh đến mức máu mũi bắn tung tóe lên nền đá cẩm thạch bóng loáng.",
    "Mấy tên áo đen đang đánh hăng thì một chiếc Maserati tắp vào cửa tòa nhà. Hai tên áo đen nhấc bổng Quách Quân tới trước đầu xe. Cửa xe mở ra, một kiều nữ ăn mặc sang trọng bước xuống.",
    "“Là vị nữ khách hàng xinh đẹp đã đệ đơn khiếu nại Quách Quân quấy rầy đấy.” Lý Nhẹ Nhàng nhận ra người nữ nhân nọ.",
    "Người mỹ nữ vung tay tát một cái tát giòn giã vào mặt Quách Quân. Tiếng “bốp” vang dội tới mức khiến Khương Tri Uẩn và đám người xung quanh hóng hớt đều giật mình lùi lại một bước.",
    "“Đừng bao giờ xuất hiện ở thành phố C nữa.”",
    "Khương Tri Uẩn thì thào thì thầm, không ai nghe thấy từng từ cô thốt ra hoàn toàn trùng khớp với từng từ người mỹ nữ kia vừa nói.",
    "“Hả? Cậu nói gì cơ?” Lý Nhẹ Nhàng nghe không rõ.",
    "“Không có gì đâu.” Khương Tri Uẩn nhìn người mỹ nữ cùng đám người áo đen quẳng Quách Quân xuống đất rồi lên xe phóng đi mất, chỉ còn lại một mình Quách Quân nằm rên rỉ đau đớn trước cửa tòa nhà.",
    "Mọi chuyện vừa mới xảy ra hoàn toàn y hệt như thước phim cô đã nhìn thấy trong đầu khi chạm vào Quách Quân lúc nãy.",
    "Tại sao cô lại có thể nhìn thấy trước những chuyện chưa xảy ra cơ chứ? Chẳng lẽ cô thực sự sở hữu một khả năng đặc biệt nào đó?",
    "“Đi thôi.” Lý Nhẹ Nhàng thấy bảo an thong thả tới nơi kéo Quách Quân đi, không còn trò hay để xem nữa liền kéo Khương Tri Uẩn trở lại công ty.",
    "“Cái tên Quách Quân này hễ thấy gái đẹp là mắt sáng rỡ, lần này rốt cuộc cũng đụng phải đá hộc rồi!” Lý Nhẹ Nhàng ngồi vào chỗ làm việc vẫn không quên dè bỉu Quách Quân.",
    "Mấy đồng nghiệp bên cạnh nghe thấy liền sán lại nhiều chuyện: “Sao thế sao thế?”",
    "Lý Nhẹ Nhàng thể hiện năng khiếu kể chuyện như diễn giả, miêu tả lại diễn biến dưới lầu một cách vô cùng sống động. Đồng nghiệp vây lại hóng hớt ngày một đông.",
    "Mọi người bắt đầu xúm vào chỉ trích Quách Quân, bởi vì hầu như những nữ sinh xinh đẹp trong công ty đều từng bị hắn giở trò quấy rầy, trong đó Khương Tri Uẩn là xinh đẹp nhất và cũng bị làm phiền thảm nhất.",
    "Nhân vật chính Khương Tri Uẩn lại đang nhìn Lý Nhẹ Nhàng đến thẫn thờ. Nếu cô thực sự cứ chạm vào ai là nhìn thấy người đó sắp xảy ra chuyện gì, vậy tại sao lúc nãy chạm vào Lý Nhẹ Nhàng lại chẳng thấy gì hết?",
    "Đang suy nghĩ nhập thần thì một cô đồng nghiệp nhóm bên cạnh đứng nghe chuyện vui vẻ thuận tay khoác vai Khương Tri Uẩn. Cô quay sang nhìn, là đồng sự tổ kế bên, vốn không tiếp xúc nhiều.",
    "Khương Tri Uẩn vỗ nhẹ lên bàn tay đang đặt trên vai mình. Ùm, trong đầu vẫn không xuất hiện bất kỳ hình ảnh nào. Cái năng lực này sao lại lúc ẩn lúc hiện thế nhỉ?",
    "Ăn dưa hóng hớt ở công ty cả một ngày, mãi đến khi hoàng hôn buông xuống Khương Tri Uẩn mới trở về tới tiểu khu dưới nhà. Vừa chuẩn bị bước vào thang máy thì thấy bạn trai của Trần Quyên xách đồ vội vã từ trong thang máy bước ra.",
    "Nhớ tới hình ảnh nhìn thấy ở thang máy buổi sáng, Khương Tri Uẩn liền lên tiếng gọi anh ta lại.",
    "“Anh làm sao thế? Chị Trần Quyên đâu rồi ạ?”",
    "Bạn trai Trần Quyên thấy là Khương Tri Uẩn liền dừng bước: “Quyên Quyên bị trượt chân ngã ở cầu thang bộ công ty, tối nay anh phải vào viện chăm sóc cô ấy.”",
    "“Hả!” Khương Tri Uẩn lần này thực sự bị dọa cho giật mình: “Có nghiêm trọng lắm không anh?”",
    "“Bị nứt xương nhẹ.”",
    "“Nghiêm trọng thế cơ ạ!”",
    "Bạn trai Trần Quyên nhìn đồng hồ, vẻ mặt sốt ruột: “Anh không nói chuyện với em nữa nhé, anh không yên tâm để Quyên Quyên ở một mình trong bệnh viện.”",
    "“Dạ vâng vâng, anh mau đi đi ạ. Nếu cần hỗ trợ gì anh cứ bảo chị Trần Quyên liên hệ với em nhé.”",
    "“Cảm ơn em nhé.” Cảm ơn xong, bạn trai Trần Quyên xách đồ rảo bước nhanh ra khỏi tiểu khu.",
    "Bước chân Khương Tri Uẩn cứng đờ dịch chuyển về căn hộ. Cô ngồi thẫn thờ trên ghế sô-pha như kẻ mất hồn. Nhớ tới những tai nạn mà Trần Quyên và Quách Quân gặp phải sau khi cô chạm vào họ, tất cả đều đã thực sự xảy ra trong đời thực.",
    "Cô thực sự sở hữu khả năng đặc biệt sao? Chẳng lẽ đây chính là dị năng trong các cuốn tiểu thuyết mạt thế? Cô chạm vào ai là có thể dự đoán được tai nạn sắp xảy ra với người đó?",
    "Sao cảm thấy cái năng lực này có chút xui xẻo thế nhỉ.",
    "Điều này quá mức huyền huyễn rồi!",
    "Khương Tri Uẩn có chút ngơ ngác. Cô nằm vật ra ghế sô-pha, lấy điện thoại ra theo bản năng bấm số gọi cho người nọ. Từ nhỏ đến lớn, anh luôn là người dọn dẹp rắc rối cho cô, nhưng đúng như dự đoán, điện thoại không có người bắt máy.",
    "Cũng phải thôi, anh là người ba ngày hai bận đi làm nhiệm vụ bí mật, làm sao có thể dễ dàng liên lạc được chứ. Cô chỉ có nước ngồi chờ anh chủ động liên lạc mà thôi.",
    "Nếu không phải vì thế thì cô đã chẳng giận dỗi một mình chạy tới thành phố C làm việc. Haizz, thôi không nghĩ tới anh nữa.",
    "Cô vẫn chưa hiểu rõ dị năng này. Tại sao chạm vào Lý Nhẹ Nhàng hay cô đồng nghiệp kia thì chẳng thấy gì, mà chạm vào Trần Quyên với Quách Quân thì lại thấy tai nạn sắp xảy ra? Chẳng lẽ là vì dạo này họ đều bình an vô sự?",
    "Xem ra ngày mai phải tìm thêm vài người để thử nghiệm mới được.",
    "Không hiểu sao hôm nay cô cảm thấy mệt mỏi kỳ lạ. Khương Tri Uẩn làm đơn giản chút gì đó bỏ bụng, rửa mặt đánh răng xong là leo lên giường ngủ ngay.",
    "Đêm đã về khuya.",
    "Nằm trên giường, Khương Tri Uẩn đã chìm vào giấc ngủ sâu. Chiếc đèn ngủ nhỏ đầu giường vẫn tỏa ra ánh sáng tù mù, không gian xung quanh tĩnh mịch tờ mờ. Khương Tri Uẩn đột nhiên cau chặt mày, hai tay bất an nắm chặt lấy chiếc chăn, trong miệng bắt đầu lẩm bẩm tự nói.",
    "Cô lại nằm mơ.",
    "Cô mơ thấy bản thân đang ở công ty thì đột nhiên bị một đồng nghiệp phát cuồng cào bị thương. Cô rơi vào hôn mê và được đưa tới bệnh viện. Rất nhanh sau đó, các bệnh nhân trong bệnh viện đều bắt đầu phát cuồng. Bác sĩ và y tá dưới sự bảo vệ của cảnh sát đã đưa một bộ phận bệnh nhân rút lui.",
    "Mà cô lại thức tỉnh ngay trên đường di chuyển. Lúc này virus trên toàn quốc đã toàn diện bùng phát, khắp nơi đều là những kẻ lây nhiễm điên cuồng khát máu.",
    "Cô đi theo đội cứu hộ bôn ba mất nửa năm mới trở về tới thành phố B. Thành phố B với vị thế là trung tâm cả nước lúc này đã bắt đầu ổn định trở lại, nhưng khi cô trở về khu biệt thự thì mới phát hiện nhà mình đã có người khác chuyển vào ở từ lâu.",
    "Thông qua gia đình họ Phó - người hàng xóm cũ may mắn còn sống sót, cô mới biết cha mẹ lưu thủ ở thành phố B sau khi em trai đi khỏi không lâu vì lo lắng nên đã ra ngoài tìm kiếm hai chị em. Kết quả bị kẻ lây nhiễm cắn chết ngay tại chỗ, chết không toàn thây. Hiện tại gia đình bốn người chỉ còn lại một mình cô sống sót.",
    "“Ba mẹ ơi!”",
    "Khương Tri Uẩn đột nhiên bật dậy, cảm giác thê lương tan nhà nát cửa trong giấc mơ vẫn còn đọng lại sâu sắc trong tim.",
    "Cô ngồi trên chiếc giường ấm áp mềm mại mà lại cảm thấy như đang ở trong mơ, còn giấc ác mộng tàn khốc kia lại chân thực như thể chính cô đã trải qua. Mọi chi tiết xảy ra trong giấc mơ cô đều nhớ rõ mùng một.",
    "Khương Tri Uẩn rốt cuộc đã tỉnh ngộ: Mấy ngày nay những gì cô thấy đều không phải là mơ, mà chính là dị năng tiên đoán của cô!",
    "Virus, những kẻ lây nhiễm bạo lực khát máu, sự ra đi của người thân... tất cả đều là những tai họa sắp sửa giáng xuống!"
]

chap_3_p = [
    "Chương 3 virus trước tiên bùng nổ?",
    "Khương Tri Uẩn trằn trọc suy nghĩ suốt cả một đêm. Cô cảm thấy việc đầu tiên cần làm là tuyệt đối không được để ba mẹ và em trai lên thành phố C tìm mình. Thành phố B là trung tâm cả nước, trong viễn cảnh cô nhìn thấy, thành phố B cũng là nơi khống chế được dịch bệnh nhanh nhất.",
    "Hơn nữa khu biệt thự nhà cô đang ở toàn là cán bộ quân chính đã về hưu, gần đó còn có doanh trại quân đội đóng quân, bản thân nó đã là một điểm cư trú vô cùng an toàn rồi.",
    "Trong giấc mơ, khi cô theo đội cứu hộ về tới nhà, gia đình họ Phó ở căn hộ kế bên vẫn sống khỏe mạnh bình an, thậm chí còn có thể thu lưu cô ở nhờ. Cho nên ba mẹ và em trai cứ ở lại thành phố B là an toàn nhất.",
    "Chỉ cần cô lập tức tức tốc trở về nhà, cô có thể thuyết phục người nhà cùng nhau cố thủ trong nhà, tránh được đợt bùng phát dịch bệnh thảm khốc ban đầu.",
    "Hơn nữa trong giấc mơ tuy có mốc thời gian mơ hồ là ba tháng sau, nhưng virus là thứ biến ảo khôn lường, vạn nhất nó bùng phát sớm hơn thì sao? Cô lại đang ở đúng thành phố C - nơi bùng dịch nghiêm trọng nhất, đến lúc đó có mọc thêm cánh cũng khó lòng thoát khỏi.",
    "Nói là làm, Khương Tri Uẩn định mở ứng dụng đặt chuyến bay sớm nhất về thành phố B thì điện thoại của Lý Nhẹ Nhàng bất ngờ gọi tới.",
    "“Alo?”",
    "“Tri Uẩn! Cậu giúp tớ với!” Giọng Lý Nhẹ Nhàng tràn ngập sự hốt hoảng.",
    "“Có chuyện gì thế? Cậu bình tĩnh từ từ nói xem nào.”",
    "“Ba tớ bị bệnh rồi, sốt cao không hạ. Bệnh viện số 2 gần nhà tớ nói không chữa được, bảo nhà tớ phải chuyển viện sang Bệnh viện Nhân dân thành phố C. Nhưng Bệnh viện Nhân dân đã quá tải không còn giường bệnh nào nữa. Tớ nhớ cậu có quen một bác sĩ ở đó, cậu có thể giúp tớ liên hệ thử xem được không? Tớ xin cậu đấy.”",
    "Nghe tiếng Lý Nhẹ Nhàng đã bắt đầu nghẹn ngào bật khóc, Khương Tri Uẩn vội vàng trấn an: “Bệnh viện sẽ không bỏ mặc bệnh nhân đâu, cậu đừng gấp, tớ lập tức giúp cậu liên hệ ngay.”",
    "Lý Nhẹ Nhàng nghe Khương Tri Uẩn một lời nhận lời giúp đỡ thì cảm động tới mức không gì sánh bằng: “Cảm ơn cậu, thực sự cảm ơn cậu rất nhiều Tri Uẩn!”",
    "Khương Tri Uẩn cúp máy rồi bấm số gọi cho Tằng Nhạc Ngôn. Đây là một nữ bác sĩ khoa ngoại cô quen biết trong một lần tham gia hoạt động, hiện đang công tác tại Bệnh viện Nhân dân thành phố C. Tằng Nhạc Ngôn chỉ lớn hơn cô năm tuổi, tuổi đời còn trẻ nhưng đã là nhân tố trọng điểm được khoa phòng bồi dưỡng.",
    "Khương Tri Uẩn quen biết Tằng Nhạc Ngôn là vì sau sự kiện nọ, cô đã cứu Tằng Nhạc Ngôn khi chị ấy bị xe điện đâm trúng rồi bỏ chạy trên một con đường hẻm vắng vẻ. Tuy nhiên một người là bác sĩ khoa ngoại, một người là dân văn phòng tài chính, cả hai đều bận túi bụi nên dù ở cùng một thành phố cũng hiếm khi gặp mặt, nhưng tình cảm bạn bè vẫn vô cùng bền chặt.",
    "“Bác sĩ Tằng!” Điện thoại chuông reo một hồi lâu rốt cuộc cũng có người bắt máy.",
    "“Tri Uẩn, có chuyện gì thế em?” Tằng Nhạc Ngôn kẹp điện thoại bên tai, tay vẫn không ngừng ký tên vào xấp bệnh án mà y tá đưa tới.",
    "Khương Tri Uẩn nghe thấy âm thanh ồn ào hỗn loạn ở đầu dây bên kia, như thể có rất đông người, cô liền đi thẳng vào vấn đề: “Ba của bạn em bị sốt cao không hạ, Bệnh viện số 2 bảo chuyển sang Bệnh viện Nhân dân nhưng lại không còn giường bệnh nữa rồi.”",
    "“Bác ấy cũng sốt cao không hạ à?” Tằng Nhạc Ngôn kinh ngạc, đổi điện thoại sang tai trái: “Em bảo họ đưa bác ấy tới đây đi, chị sẽ nghĩ cách điều phối dồn cho bác ấy một cái giường.”",
    "“Cảm ơn chị nhiều lắm bác sĩ Tằng, tụi em sẽ đưa bác ấy tới ngay!”",
    "“Được.” Tằng Nhạc Ngôn vừa dứt lời thì Khương Tri Uẩn đã nghe thấy đầu dây bên kia có người lớn tiếng gọi Tằng Nhạc Ngôn: “Tri Uẩn, khi nào tới bệnh viện thì gọi cho chị nhé, chị phải đi bận tiếp đây.”",
    "Chữ “Vâng” còn chưa kịp thốt ra thì Tằng Nhạc Ngôn đã cúp máy, xem ra công việc thực sự vô cùng bận rộn.",
    "Bên này đã chốt xong, Khương Tri Uẩn vội vã liên hệ với Lý Nhẹ Nhàng, bảo cô ấy đưa cha tới Bệnh viện Nhân dân ngay, cô ở gần đó hơn nên sẽ tới cổng chờ trước. Lý Nhẹ Nhàng ở đầu dây bên kia cảm động rớt nước mắt, cúp điện thoại xong liền vội giục người nhà làm thủ tục chuyển viện cho cha.",
    "Khương Tri Uẩn vừa tới Bệnh viện Nhân dân liền thấy xe cứu thương hú còi inh ỏi ra ra vào vào liên tục. Rất nhiều người nhà đang cuống quít khiêng người bệnh vào cấp cứu, nhân viên y tế chạy đôn chạy đáo khắp nơi, toàn bộ bệnh viện hỗn loạn tới mức nghẹt thở.",
    "Cô cảm thấy có điều gì đó không ổn. Lượng bệnh nhân thế này có phải là quá nhiều rồi không?",
    "Chưa kịp suy nghĩ sâu thêm thì chiếc xe cứu thương tiếp theo dừng lại. Lý Nhẹ Nhàng bước xuống xe, vừa thấy Khương Tri Uẩn đứng ở cổng là vẫy tay điên cuồng.",
    "Khương Tri Uẩn vội gọi cho Tằng Nhạc Ngôn. Lần này điện thoại bắt máy rất nhanh, Khương Tri Uẩn còn chưa kịp cất lời thì Tằng Nhạc Ngôn đã buông một câu: “Chị ra ngay đây!” rồi cúp máy.",
    "Lý Nhẹ Nhàng cùng người nhà đẩy chiếc giường cấp cứu có Lý phụ đang nằm tới trước mặt Khương Tri Uẩn, cuống quít nói lời cảm ơn: “Tri Uẩn, thực sự cảm ơn cậu nhiều lắm!”",
    "“Đúng vậy, cảm ơn cháu nhiều lắm cô gái ơi!” Mẹ của Lý Nhẹ Nhàng trực tiếp tiến lên nắm chặt lấy hai tay Khương Tri Uẩn, ánh mắt tràn đầy sự biết ơn.",
    "“Đáy là việc nên làm mà bác và Nhẹ Nhàng ơi, bệnh tình của chú mới là quan trọng nhất, mọi người đừng khách khí quá.” Khương Tri Uẩn nhìn Lý phụ nằm trên giường cấp cứu hai mắt nhắm nghiền, hai má đỏ bừng, toàn thân nóng hổi như ngọn lửa.",
    "“Chú vẫn ổn chứ ạ?”",
    "“Không ổn chút nào.” Lý Nhẹ Nhàng nhìn người cha đang hôn mê, nước mắt lập tức trào ra như mưa.",
    "“Đừng gấp, rồi sẽ ổn thôi mà.” Khương Tri Uẩn tiến lên đỡ lấy Lý Nhẹ Nhàng.",
    "“Tri Uẩn.” Khương Tri Uẩn nghe tiếng ngẩng đầu lên, Tằng Nhạc Ngôn trong bộ áo blouse trắng đang rảo bước chạy về phía cô.",
    "Tằng Nhạc Ngôn tiến lại gần, chẳng kịp chào hỏi xã giao mà lập tức kiểm tra tình trạng của Lý phụ: “Tình hình không tốt lắm.” Chị giơ tay vẫy mấy y tá, vội vã dặn dò: “Đưa vào Khu bệnh 2 trước!”",
    "Mẹ con Lý Nhẹ Nhàng chẳng kịp chào tạm biệt Khương Tri Uẩn, vội vã đẩy chiếc giường cấp cứu đi theo. Tằng Nhạc Ngôn bước đi vài bước, suy nghĩ một chút rồi xoay người kéo Khương Tri Uẩn sang một góc vắng.",
    "“Sao thế chị?” Khương Tri Uẩn ngơ ngác.",
    "Tằng Nhạc Ngôn quan sát xung quanh, ghé sát vào tai Khương Tri Uẩn thì thầm: “Tình hình vô cùng bất thường. Toàn thành phố đột nhiên xuất hiện rất nhiều người sốt cao không hạ, dùng bất kỳ loại kháng sinh nào cũng không có tác dụng. Bệnh viện chúng chị đã quá tải từ lâu rồi.”",
    "“Cái gì?” Chẳng lẽ dịch bệnh đã bắt đầu bùng phát rồi sao? Khương Tri Uẩn chấn động kinh hãi.",
    "“Hạn chế tới bệnh viện thôi em nhé. Ngày thường ít ra ngoài, đeo khẩu trang cẩn thận và chú ý khử trùng.”",
    "“Ý chị là sao? Chị cảm thấy căn bệnh này có tính lây nhiễm ạ?”",
    "“Hiện tại chưa ghi nhận hiện tượng lây từ người sang người, nhưng loại virus này xuất hiện quá đột ngột. Số lượng người nhiễm ở thành phố C cực kỳ đông, chúng chị đã báo cáo lên cấp trên rồi.”",
    "Tằng Nhạc Ngôn không giấu Khương Tri Uẩn, nói thẳng suy đoán của mình: “Chị cảm thấy đây không phải là sốt thông thường. Tiến triển bệnh tiếp theo có thể sẽ có biến động rất lớn, chị có cảm giác vô cùng bất an.”",
    "Nói tới đây Tằng Nhạc Ngôn ngập ngừng một chút: “Chị nhớ nhà em ở thành phố B đúng không? Bên này nếu không có việc gì quan trọng thì em hãy mau chóng thu xếp về thành phố B ngay đi.”",
    "Nói ra những lời này Tằng Nhạc Ngôn đã phải mạo rủi ro rất lớn. Hàm ý sâu xa trong đó Khương Tri Uẩn nghe một cái là hiểu ngay. Không ngờ virus đã bắt đầu lây lan từ lúc này, vậy thì thành phố C sắp sửa trở thành nơi nguy hiểm khôn lường rồi.",
    "Nhớ tới giấc mơ tiên đoán của mình, Khương Tri Uẩn lập tức nắm chặt lấy tay Tằng Nhạc Ngôn khi chị định xoay người bước đi. Cô biết mình không thể thay đổi được đại cục, nhưng trong khoảnh khắc này, cô rất muốn kéo người bạn bác sĩ tốt bụng đã cảnh báo mình rời khỏi vũng lầy.",
    "“Chị đi cùng em đi! Em định đặt vé máy bay về thành phố B ngay bây giờ đây.”",
    "Tằng Nhạc Ngôn mỉm cười cảm động. Khương Tri Uẩn quả thực là một cô gái vô cùng tốt bụng. Năm đó nếu không nhờ cô đi ngang qua cứu chị khi chị bị xe đâm hôn mê, chị không biết mình sẽ nằm gục trên đường bao lâu nữa.",
    "Nhưng chị không thể đi được.",
    "“Chị là bác sĩ.” Tằng Nhạc Ngôn kiên định gỡ tay Khương Tri Uẩn ra.",
    "Nhìn ánh mắt kiên cường của Tằng Nhạc Ngôn, những lời khuyên lăm lăm trong họng Khương Tri Uẩn đành nuốt ngược trở vào.",
    "“Chú ý phòng hộ cẩn thận nhé.” Tằng Nhạc Ngôn không biết liệu sau này có còn gặp lại Khương Tri Uẩn nữa hay không, chị lại mỉm cười với cô, giọng trầm xuống: “Mau đi đi!”",
    "Nói xong, Tằng Nhạc Ngôn không chút do dự quay người bước về phía cổng chính bệnh viện. Dáng đi vội vã khiến tà áo blouse trắng tung bay trong gió. Giờ phút này, chị giống như một vị nữ tướng quân dũng cảm lao ra chiến trường.",
    "Điều này khiến Khương Tri Uẩn nhớ tới người nam nhân ấy cũng từng kiên định nói với cô rằng anh là một người lính. Trước đây cô không hiểu, nhưng giờ đây dường như cô đã bắt đầu hiểu ra phần nào."
]

chap_4_p = [
    "Chương 4 biến dị người lây nhiễm xuất hiện",
    "Nhìn bóng lưng Tằng Nhạc Ngôn khuất dần trước mắt, Khương Tri Uẩn không kịp cảm xúc lâu, vội lấy điện thoại ra đặt chuyến bay sớm nhất về thành phố B. Chuyến bay cất cánh sau bốn giờ nữa, thời gian vẫn còn kịp để cô quay về căn hộ dọn dẹp chút đồ đạc.",
    "Trở về căn hộ, lấy chiếc vali ra, nhìn ngắm căn hộ nhỏ cô đã gắn bó gần hai năm, Khương Tri Uẩn có chút lưu luyến không đành. E rằng sau này sẽ không còn cơ hội quay trở lại nơi này nữa.",
    "Cô muốn mang đi tất cả mọi thứ, nhưng chiếc vali chỉ có thể chứa được bấy nhiêu, đành phải ưu tiên chọn lựa quần áo thu xếp. Lúc này cô mới khao khát có được một không gian tùy thân như trong các cuốn tiểu thuyết.",
    "Để tránh đêm dài lắm mộng, Khương Tri Uẩn dọn hành lý xong là lập tức bắt xe ra thẳng sân bay. Vừa bước vào nhà ga sân bay, Khương Tri Uẩn đã nhận ra điểm bất thường.",
    "Ngày thường đi lại bằng xe riêng cô không cảm nhận rõ, giờ bước vào khu vực đông đúc như sân bay, cô mới phát hiện những hành khách qua lại ai nấy đều mặt mày đỏ bừng, dáng vẻ mệt mỏi ốm yếu. Cảnh tượng đó dọa cô sợ tới mức vội vàng lấy khẩu trang ra đeo kín.",
    "Máy bay còn một giờ nữa mới cất cánh. Ở thành phố C việc lây lan virus đã rộng khắp như vậy, thì thành phố B e rằng cũng chẳng an toàn được bao lâu. Cần phải thông báo cho người nhà sớm chuẩn bị mới được. Khương Tri Uẩn cầm điện thoại gọi cho em trai.",
    "“Chị?”",
    "“Biết Nguyên, chị đã đặt vé máy bay về thành phố B rồi, một giờ nữa là cất cánh.”",
    "Khương Biết Nguyên bật dậy khỏi ghế sô-pha: “Chị sắp về nhà rồi ạ! Sao không nói trước với em một tiếng để em ra sân bay đón chị?”",
    "“Đừng gấp.” Khương Tri Uẩn nghĩ đến việc chỉ ba giờ nữa là được gặp lại người nhà, trong lòng cũng dấy lên niềm mong chờ. Nhưng cô vẫn còn chính sự quan trọng cần giao cho em trai làm.",
    "“Em không cần ra sân bay đón chị đâu, chị có việc quan trọng này giao cho em đây.” Vừa nói Khương Tri Uẩn vừa quan sát xung quanh. Vừa vào sân bay thấy mọi người có vẻ đau ốm nên cô đã cố tình tìm một góc vắng ngồi xuống, xung quanh không có mấy ai.",
    "Nhưng cô vẫn đè thấp giọng xuống: “Ở thành phố C hiện đang bùng phát một loại virus nguy hiểm, diện lây lan cực kỳ rộng, ước tính sẽ nhanh chóng bùng phát quy mô lớn. Chị bạn bác sĩ khuyên chị phải mau chóng rời khỏi thành phố C ngay lập tức.”",
    "“Cái gì! Thế chị có sao không chị, sao tụi em lại không nghe tin tức gì hết thế?”",
    "Là người từng trải qua các đợt dịch bệnh trên cả nước, Khương Biết Nguyên thừa hiểu mức độ đáng sợ của việc virus lây lan.",
    "“Chị không sao. Nhưng chị cảm giác virus đã bắt đầu lây lan ra bên ngoài rồi, hoặc nói đúng hơn là không chỉ riêng thành phố C có virus đâu. Thành phố B e rằng cũng khó thoát khỏi. Ngay bây giờ em hãy lập tức ra ngoài tích trữ dược phẩm phòng dịch và thực phẩm, mua được bao nhiêu hay bấy nhiêu!”",
    "“Thế còn chị thì sao chị?”",
    "“Chỉ ba giờ nữa là chị đáp xuống thành phố B rồi, em không cần lo cho chị. Việc quan trọng nhất của em lúc này là đi tích trữ vật tư, sau đó giữ ba mẹ ở yên trong nhà, tuyệt đối không được ra ngoài cho tới khi chị về!”",
    "“Thế em ra sân bay đón chị nhé.”",
    "“Em đừng tới! Nếu virus đã lây lan ra ngoài thì sân bay chính là đầu mối giao thông có nguy cơ bây nhiễm lớn nhất. Em cứ ngoan ngoãn ở yên trong nhà, cũng đừng để ba mẹ đi đâu hết.”",
    "“Nhưng mà chị...”",
    "“Không nhưng nhị gì hết, nghe lời chị! Nếu em không tranh thủ lúc dịch bệnh chưa bùng phát diện rộng đi tích trữ vật tư, thì tới lúc chị về em định cho chị uống gió Tây Bắc chắc? Tin chị đi, mọi người ở nhà đợi chị là an toàn nhất.”",
    "“Được rồi, em nghe chị. Chị nhất định phải chú ý an toàn đấy nhé.”",
    "“Phải rồi,” Khương Tri Uẩn nhớ tới nhà họ Phó ở căn hộ kế bên. Tuy gia đình họ toàn người làm chính trị hoặc trong quân ngũ, tin tức chắc chắn linh thông hơn nhà cô, nhưng hiện tại tin tức chưa lan tới thì chắc họ cũng chưa chuẩn bị gì.",
    "“Cái cậu Phó Chinh có ở nhà không em?”",
    "“Có chị, tụi em vừa cày game xong, cậu ấy mới về nhà nghỉ ngơi.”",
    "“Thế em kéo cả Phó Chinh đi mua vật tư cùng luôn đi.”",
    "Khương Biết Nguyên biết chị gái sẽ không bỏ quên nhà họ Phó. Hai gia đình lớn lên bên nhau từ nhỏ, thân thiết như người một nhà. Chỉ là: “Thế chuyện virus lây lan có nói cho cậu ấy biết không chị?”",
    "“Nói chứ. Tin tức nhà cậu ấy chắc chắn linh thông hơn nhà mình, chỉ là tình hình thành phố C chưa rõ ràng nên chưa truyền tới thôi. Với cả bây giờ chúng ta tích trữ vật tư không thể quá phô trương, em hiểu ý chị chứ Biết Nguyên?”",
    "“Em hiểu rồi, tụi em sẽ cẩn trọng hành sự.”",
    "“Được rồi, thế em đi mau đi, chị đáp xuống đất sẽ gọi cho em.”",
    "“Chị nhớ phải cẩn thận đấy.” Khương Biết Nguyên cúp máy, ngay lập tức lao sang nhà kế bên tìm Phó Chinh.",
    "Không biết có phải ảo giác của cô hay không, nhưng dường như chỉ trong thời gian một cuộc điện thoại, tiếng ho xung quanh đã trở nên dồn dập hơn.",
    "Khương Tri Uẩn cẩn thận quan sát xung quanh, phát hiện không chỉ hành khách kéo vali ho không ngừng, mà ngay cả nhiều nhân viên sân bay cũng bắt đầu xuất hiện triệu chứng mệt mỏi ốm yếu. Tình hình thực sự rất bất thường, cảm giác virus không còn ở thời kỳ ủ bệnh nữa mà đã bắt đầu bùng phát rồi.",
    "Nếu đúng như giấc mơ tiên đoán của cô, virus bùng phát thì những kẻ nhiễm bệnh sẽ nhanh chóng biến dị và tấn công con người. Nếu một hồi nữa trên máy bay có kẻ nhiễm virus biến dị thì cô biết trốn đi đâu?",
    "Thế nhưng tình hình sân bay đã nghiêm trọng thế này, trong nội thành chắc chắn còn nguy hiểm hơn. Nếu bây giờ không lên máy bay thì e rằng sẽ không còn chuyến nào nữa. Khương Tri Uẩn suy nghĩ hồi lâu, cuối cùng quyết định mạo hiểm lên máy bay. Nếu may mắn, cô sẽ về tới thành phố B ngay lập tức.",
    "Đúng lúc này, loa phát thanh thông báo tới giờ lên máy bay. Khương Tri Uẩn kéo chiếc vali nhỏ bước vào hàng xếp hàng. Cô chủ động giữ khoảng cách với người phía trước và phía sau, lặng lẽ quan sát mọi người xung quanh.",
    "Phía trước cô là một người anh trai cao lớn, phía sau là một gia đình ba người đi cùng con gái. Nom họ đều rất khỏe mạnh, không có dấu hiệu đau ốm.",
    "Cô thở phào một hơi, yên tâm xếp hàng.",
    "Chẳng ai ngờ được, chỉ còn hai người nữa là tới lượt cô thì người phụ nữ phía trước anh trai cao lớn lại xảy ra tranh chấp với nhân viên mặt đất.",
    "“Cô ơi, xin cô vui lòng xuất trình căn cước công dân ạ.”",
    "“Căn cước của tôi vừa mới để trong túi xách mà.” Người phụ nữ cúi đầu lục lọi túi.",
    "“Thế thẻ lên máy bay của cô còn không ạ?”",
    "Người phụ nữ mếu máo: “Thẻ lên máy bay để chung với căn cước, giờ không thấy đâu nữa rồi!”",
    "Nhân viên mặt đất có vẻ đã quen với các sự cố bất ngờ, thản nhiên lên tiếng: “Vậy mời cô bước sang bên cạnh, chúng tôi sẽ cử nhân viên hỗ trợ cô đổi chuyến ạ.”",
    "“Cô nói thế là ý gì? Tôi không được lên máy bay đúng không!”",
    "“Cô không xuất trình được giấy tờ hợp lệ thì không thể lên máy bay ạ.”",
    "Chẳng ai ngờ người phụ nữ đột ngột bộc phát cảm xúc dữ dội: “Không được! Tôi bắt buộc phải lên máy bay! Tôi phải về thành phố B!” Nói rồi người phụ nữ lao thẳng về phía ống lồng lên máy bay.",
    "Mấy nhân viên mặt đất vội vàng tiến lên ngăn cô ta lại. Trong lúc giằng co, cảm xúc của người phụ nữ ngày càng kích động, gào hú lớn tiếng. Hành khách xếp hàng phía sau đều xúm lại xem náo nhiệt.",
    "Không xong rồi!",
    "Khương Tri Uẩn nhận ra đầu của người phụ nữ nọ bắt đầu giật giật một cách bất nhiên, khuôn mặt ngày càng đỏ bừng, mắt sưng to lên, vệt máu đỏ quạch phủ kín lòng trắng, thậm chí nước bọt bắt đầu nhỏ giọt không kiểm soát được.",
    "Cô ta đang biến dị!",
    "Khương Tri Uẩn lập tức kéo vali lùi về sau. Nào ngờ gia đình ba người phía sau lại đang nhoài người về trước hóng chuyện, cô kéo vali lùi lại lại bị đám người phía sau đẩy ngược về phía trước.",
    "“Á!”",
    "Không kịp nữa rồi. Khương Tri Uẩn nhìn thấy người phụ nữ phía trước đã bạo khởi lao tới, bắt lấy cô nhân viên mặt đất đang cản đường, đột ngột cắn một cú thật mạnh vào cánh tay cô ấy, máu tươi lập tức bắn tung tóe.",
    "Cô nhân viên gào lên đau đớn. Đồng nghiệp xung quanh vội tiến lên gỡ ra, ai ngờ người phụ nữ cắn chặt không nhả, đột ngột xé phăng một mảng thịt lớn trên cánh tay cô nhân viên.",
    "Người phụ nữ ngẩng đầu lên, khuôn miệng đầy máu tươi vẫn đang nhai nhấu. Đám đông lập tức bị cảnh tượng quái đản máu me này dọa cho hồn xiêu phách lạc, chen nhau tháo chạy tán loạn.",
    "“Cắn người rồi!”",
    "“Bệnh dại rồi!”",
    "Khương Tri Uẩn cũng vội vàng tháo chạy về phía sau. Nhưng vì ban nãy bị đám đông đẩy lên phía trước, trong lúc mọi người hỗn loạn chen chúc tháo chạy, cô không biết bị ai huých mạnh một cái ngã ngửa ra đất.",
    "Chưa kịp chồm dậy thì mùi máu nồng nặc đã xộc thẳng vào mũi..."
]

chap_5_p = [
    "Chương 5 bị biến dị người lây nhiễm trảo thương!",
    "Không đến mức xui xẻo thế chứ? Khương Tri Uẩn cẩn thẩn ngẩng đầu lên thì thấy người phụ nữ mặt đầy máu tươi đang trừng mắt nhìn mình.",
    "“Ực” một tiếng, miếng thịt người trong miệng cô ta đã bị nuốt chửng. Khương Tri Uẩn nén cảm giác buồn nôn đang dâng lên tận cổ họng, gắt gao nhìn chằm chằm người phụ nữ, chậm rãi nhích người về sau.",
    "Vừa lùi được hai bước thì phía sau không biết là ai thốt lên một tiếng thét chói tai, lần nữa kích thích người phụ nữ. Cô ta há cái miệng rộng máu me giương nanh lao thối về phía Khương Tri Uẩn đang nằm trên đất.",
    "Trong khoảng khoảnh khắc sinh tử, Khương Tri Uẩn không biết lấy đâu ra sức lực, một tay nhấc bổng chiếc vali du lịch nhỏ dùng hết toàn lực ném thẳng vào mặt người phụ nữ.",
    "Chiếc vali trúng đích làm người phụ nữ ngã ngửa ra sau. Khương Tri Uẩn nắm lấy cơ hội dùng cả tay lẫn chân chồm dậy tháo chạy về phía sau. Cô dốc sức chạy một hơi mấy chục mét thì vừa lúc gặp đội đặc cảnh trang bị tận răng kéo tới.",
    "Một đội đặc cảnh huấn luyện bài bản cầm khiên chắn vây chặt lấy người phụ nữ cuồng bạo đang đuổi theo Khương Tri Uẩn. Máu trên mặt cô ta vẫn chưa khô, từng giọt nhỏ xuống sàn. Cô ta giương nanh múa vuốt gầm hống đâm sầm vào khiên chắn của đặc cảnh.",
    "“Cẩn thận đừng để cô ta cắn trúng!” Khương Tri Uẩn lập tức cất tiếng nhắc nhở.",
    "“Lùi lại phía sau, đừng tiến lại gần!” Một sĩ quan đặc cảnh giữ Khương Tri Uẩn che chắn ở phía sau.",
    "Khương Tri Uẩn sợ họ chủ quan bị cắn thương nên lại hô lên: “Cô ta có thể đang mang bệnh truyền nhiễm!”",
    "Các đặc cảnh khựng lại một chút. Người sĩ quan che chở cô kinh ngạc ngoái đầu nhìn cô một cái.",
    "May mắn thay lời nhắc nhở đã phát huy tác dụng. Các đặc cảnh khống chế người phụ nữ xuống đất, lấy vật gì đó nhét chặt miệng cô ta lại, hai tay bị bẻ ngoặt khóa ngoặt phía sau. Người phụ nữ tạm thời mất đi khả năng tấn công.",
    "Khương Tri Uẩn trút được gánh nặng, cảm thấy toàn thân bủn rủn không còn chút sức lực nào, chân đau nhói định ngã gục xuống đất thì sĩ quan đặc cảnh phía trước vội vàng đỡ lấy cô.",
    "“Cô bị thương rồi! Cáng cứu thương đâu!” Sĩ quan đặc cảnh hô lớn.",
    "“Tôi không...” Khương Tri Uẩn cúi đầu nhìn xuống thì thấy trên cánh tay một vết cào đỏ ửng đang rỉ máu tươi. Thì ra lúc nãy trong lúc hỗn loạn cô đã bị người phụ nữ cào bị thương, thế mà cô còn tưởng mình chạy rất nhanh.",
    "Xong rồi, cô thầm nghĩ, không ngờ có dị năng mà mình lại là kẻ làm pháo hôi đầu tiên. Khương Tri Uẩn dùng hết sức lực còn lại nắm lấy tay vị đặc cảnh đỡ mình: “Tôi là người nhà của bác sĩ Tằng Nhạc Ngôn ở Bệnh viện Nhân dân, hãy đưa tôi tới Bệnh viện Nhân dân...” Nói xong cô liền hôn mê bất tỉnh.",
    "Thành phố B.",
    "Khương Biết Nguyên cúp điện thoại của chị gái là lập tức lao sang nhà họ Phó, tóm lấy Phó Chinh đang ngủ nướng kéo xềnh xệch ra ngoài.",
    "“Làm cái gì thế hả em, áo tôi sắp bị cậu xé rách rồi đấy!” Phó Chinh một tay giữ cổ áo sợ bị Khương Biết Nguyên làm siết cổ.",
    "“Đi mua đồ!”",
    "Một đường phóng xe như chớp giật, Phó Chinh nhìn siêu thị đại lý bán sỉ quy mô lớn bên ngoài mà cạn lời: “Mua đồ thôi mà, có cần phải vội vã như thế không?”",
    "Khương Biết Nguyên đỗ xe xong, quan sát xung quanh không có ai liền nói: “Những lời tớ sắp nói ra đây, cậu tuyệt đối đừng ngắt lời tớ.”",
    "Phó Chinh thấy Khương Biết Nguyên trịnh trọng như vậy cũng thu lại dáng vẻ đùa giỡn: “Cậu nói đi.”",
    "Khương Biết Nguyên đem toàn bộ những gì Khương Tri Uẩn dặn dò kể lại một lượt. Phó Chinh càng nghe càng kinh hãi, nhưng anh phản ứng rất nhanh: “Thế chị Tri Uẩn bây giờ ra sao rồi?”",
    "“Chị tớ đang ở sân bay rồi, lúc gọi điện bảo còn một giờ nữa cất cánh, tính thời gian thì giờ chị ấy đang ở trên máy bay rồi.”",
    "“Thế thì tốt rồi. Vậy bây giờ tụi mình đi tích trữ vật tư trước?”",
    "“Ừm, trước tiên mua toàn bộ thực phẩm và đồ dùng hàng ngày mua được, sau đó về nhà chờ chị tớ.”",
    "“Nhưng chúng ta ở trong khu biệt thự, đột nhiên mua một đống đồ về kiểu gì cũng bị người ta phát hiện, chốt bảo vệ cũng sẽ kiểm tra đấy.” Phó Chinh đưa ra nghi vấn.",
    "Khương Biết Nguyên bị hỏi nghẹn họng. Cậu một lòng chỉ muốn hoàn thành lời chị dặn, mua đồ cho xong chứ chưa tính tới việc mang về nhà cất giấu thế nào: “Thế giờ làm sao?”",
    "Phó Chinh cạn lời: “Tóm lại là cậu chưa tính toán gì đã kéo tớ ra đây rồi đúng không.”",
    "“Thế cậu mau nghĩ cách đi chứ!”",
    "“Cậu còn cuống lên nữa.” Phó Chinh biết Khương Biết Nguyên từ nhỏ tính tình thẳng thắn không biết xoay xở, lần này nghe tin lớn như vậy thì đầu óc càng không nghĩ được nhiều.",
    "“Như thế này đi, cậu gọi một chiếc xe tải tới đây. Đồ tụi mình mua sẽ chất hết lên xe tải, sau đó đỗ xe ở gần khu đại viện. Rồi tìm cơ hội chuyển dần vật tư về nhà. Xe đồ này cứ bảo là tụi mình mua quà Tết cho công ty.”",
    "“Được đấy, vẫn là đầu óc cậu nhanh nhạy.” Khương Biết Nguyên lập tức gọi điện bảo công ty nhà mình điều một chiếc xe tải tới.",
    "Thu xếp xong xuôi, Khương Biết Nguyên và Phó Chinh tiến vào siêu thị, đi thẳng tới khu lương thực thực phẩm. Tích trữ trước gạo, bột mì, mì sợi, miến mỗi loại 50 thùng. Trong nhà nhiều nam nhân nên tích nhiều lương thực thô một chút. Lấy thêm 40 thùng dầu ăn, dầu phộng và dầu ô-liu chia đều.",
    "Sau đó mua muối, tương ớt, đường, dấm, nước tương, rượu nấu ăn, dầu hào, hạt nêm, dầu mễ mỗi loại 10 thùng.",
    "Khương Biết Nguyên đi ngang qua khu gia vị hương liệu, nhớ mẹ nấu ăn thích dùng hương liệu liền gom hết hoa tiêu, quế, trần bì, hoa hồi trên kệ mỗi thứ 3 thùng. Dù sao mấy thứ này cũng khó hỏng, giải phóng ăn không hết thì đem tặng người khác.",
    "Ở khu đồ dùng hàng ngày, cậu chỉ tay mua sữa tắm, dầu gội, nước giặt quần áo mỗi loại 20 thùng. Giấy ăn, giấy vệ sinh và khăn mặt các loại mua 40 thùng, tích trữ dùng dần.",
    "Vừa định đi thì Phó Chinh cẩn thận tích trữ cho phụ nữ trong nhà mấy chục thùng băng vệ sinh, lại thấy quần lót dùng một lần bên cạnh, hai người tiện tay mua luôn mỗi loại nam nữ 30 thùng.",
    "Rau củ quả khó bảo quản lâu nên hai người chỉ mua 10 thùng trái cây dễ bảo quản mà người nhà thích ăn, mua thêm vài thùng khoai tây, bắp cải, củ cải có thể trữ lâu. Rau ăn lá khó để lâu nên không mua.",
    "Lại sang khu đồ ăn chế biến sẵn mua mấy thùng bánh bao, màn thầu đông lạnh. Khương Biết Nguyên tiện tay gom thêm ít xúc xích đông lạnh, thịt hun khói, thịt bò dê nhúng lẩu, bò bít-tết, thịt heo, sườn heo, chân giò... Mua theo hộp vì tủ lạnh ở nhà cũng có hạn.",
    "Mua thêm 10 thùng mì ăn liền, bún ăn liền, các loại snack khoai tây, kẹo có hạn sử dụng dài mỗi loại vài thùng. Nước khoáng thùng lớn mua trực tiếp 10 thùng. Nước ngọt Coca, nước trái cây cũng lấy mỗi loại 5 thùng.",
    "Hai người bận rộn suốt ba giờ đồng hồ. Cũng may lấy cớ mua quà Tết phát cho công nhân viên nên nhân viên siêu thị nhiệt tình hỗ trợ chất đồ lên xe tải. Thấy chiếc SUV vẫn còn khoảng trống, hai người lại vào siêu thị lấy thêm ít đồ.",
    "Đang chuẩn bị lái xe về khu biệt thự thì Phó Chinh đột nhiên giữ Khương Biết Nguyên lại: “Nếu virus sớm muộn cũng bùng phát cả nước, tụi mình phải tích trữ thêm dược phẩm thông dụng và nước sát trùng nữa.”",
    "“Thế vào siêu thị khuân mấy thùng nước sát trùng ra đây, còn thuốc men thì trên đường về tụi mình ghé vào các tiệm thuốc gom dần.”",
    "“Được.” Hai người lại quay vào mua thêm mấy thùng đồ sát trùng.",
    "Cuối cùng cũng xong việc, Khương Biết Nguyên lái xe tải đi sau chiếc SUV của Phó Chinh. Thấy tiệm thuốc dọc đường là hai người tấp vào mua một đống thuốc thông dụng, khẩu trang, băng gạc y tế. Về tới đại viện thì lượng thuốc men đã chiếm nửa cốp xe.",
    "Phó Chinh tìm một tòa nhà lớn gần khu biệt thự, bảo Khương Biết Nguyên đỗ xe tải ở bãi đỗ xe ngầm rồi hai người lái SUV về khu biệt thự.",
    "Chốt bảo vệ thấy là hai người bọn họ nên không hói nhiều, chào một tiếng rồi cho qua.",
    "Khu biệt thự này nằm gần Tây Sơn thành phố B, sơn thủy hữu tình, vốn là khu nghỉ dưỡng dưỡng lão do chính phủ phối hợp với doanh nghiệp bất động sản uy tín xây dựng từ mười năm trước. Các tiêu chuẩn thiết kế đều cực kỳ kiên cố vượt trội, nhân viên bảo vệ chốt cổng đều là quân nhân giải ngũ.",
    "Môi trường tốt và an ninh nghiêm ngặt như vậy, lại gần khu quân đội đóng quân vùng ngoại ô thành phố B, nên những năm qua cũng có một số gia đình kinh doanh như nhà họ Khương chuyển tới sinh sống.",
    "Nhà họ Khương và họ Phó đều không thích người ngoài ở trong nhà, chỉ thuê người dọn dẹp theo giờ, nên Khương Biết Nguyên và Phó Chinh phải chạy mấy chuyến mới vác hết đống đồ trong xe về nhà họ Khương.",
    "Mệt nhoài nằm xoài ra ghế sô-pha nghỉ ngơi, Khương Biết Nguyên liếc nhìn đồng hồ phòng khách: “Chị tớ đáng lẽ phải đáp xuống thành phố B rồi chứ nhỉ, sao vẫn chưa gọi điện cho tớ?”",
    "Phó Chinh lấy điện thoại ra nhìn: “Đã hơn bốn tiếng rồi, cậu mau gọi cho chị Tri Uẩn đi.”",
    "“Xin lỗi, số máy quý khách vừa gọi hiện không thể liên lạc được...” Nghe tiếng báo bận trong điện thoại, Khương Biết Nguyên ngẩn người: “Không ai bắt máy.”",
    "“Cái gì?” Phó Chinh lập tức bấm số gọi thử, vẫn không có ai bắt máy.",
    "“Không liên lạc được với chị tớ, có phải thành phố C đã xảy ra chuyện rồi không?” Khương Biết Nguyên hoảng hốt tột độ.",
    "“Cái gì mà không liên lạc được với Khương Tri Uẩn?” Một giọng nói trầm thấp đầy từ tính đột nhiên vang lên ở cửa lớn."
]

def run_translation_and_qc():
    os.makedirs('data/translated', exist_ok=True)
    
    chapters = [
        ("chap_0001.txt", chap_1_p, CHAPTER_1_RAW_P_COUNT),
        ("chap_0002.txt", chap_2_p, CHAPTER_2_RAW_P_COUNT),
        ("chap_0003.txt", chap_3_p, CHAPTER_3_RAW_P_COUNT),
        ("chap_0004.txt", chap_4_p, CHAPTER_4_RAW_P_COUNT),
        ("chap_0005.txt", chap_5_p, CHAPTER_5_RAW_P_COUNT),
    ]
    
    print("=========================================================")
    print("=== TRANSLATION PIPELINE & QC AUDIT FOR 5 CHAPTERS ===")
    print("=========================================================")
    
    summary_entries = []
    
    for filename, p_list, expected_p in chapters:
        file_path = os.path.join('data/translated', filename)
        raw_path = os.path.join('data/raw_chapters', filename)
        
        with open(raw_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        content_lines = [p_list[0] + "\n\n"]
        for p in p_list[1:]:
            content_lines.append(f"{p}\n\n")
            
        translated_text = "".join(content_lines).strip() + "\n"
        
        # QC Audit
        passed, score, report = audit_chapter(raw_text, translated_text)
        print(f"\n📄 {filename}: QC Score {report['score_out_of_10']}/10 | Hanzi: {report['chinese_found_count']} | <p> match: {report['translated_paragraphs']}/{report['raw_paragraphs']}")
        
        if report['errors']:
            for err in report['errors']:
                print(f"   ⚠️ {err}")
                
        # Write translated file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
            
        print(f"   ✅ Saved to {file_path}")
        summary_entries.append(f"- **[{filename[:-4]}] {p_list[0]}**: QC Đạt {report['score_out_of_10']}/10. ({len(p_list)-1} đoạn)")

    # Update summary.txt
    summary_path = 'data/summary.txt'
    with open(summary_path, 'a', encoding='utf-8') as f:
        f.write("\n" + "\n".join(summary_entries) + "\n")
        
    print("\n✅ Cập nhật summary.txt thành công!")

if __name__ == '__main__':
    run_translation_and_qc()
