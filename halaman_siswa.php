<?php 
	session_start();

	// cek apakah yang mengakses halaman ini sudah login
	if($_SESSION['level']==""){
    header("location:index.php?pesan=gagal");
  }
 ?>
<!DOCTYPE html>
<html>
<head>
    <link rel="icon" href="icon/hexagonos.jpg">
    <title>Ujian Test</title>
    <link rel="stylesheet" href="assets/css/bootstrap.min.css">
    <script type="text/javascript" src="assets/fontawesome/js/all.js"></script>
</head>
<body>
<nav class="navbar navbar-dark bg-dark">
  <img src="icon/1.png" width="10%" class="navbar-brand">
  <!-- <form class="form-inline">
    <button class="btn btn-outline-danger my-2 my-sm-0" type="submit">Logout</button>
  </form> -->
</nav>
<br>
   <div class="container">
    <div class="alert alert-success alert-dismissible fade show text-center" role="alert">
      Halo <strong><?php echo strtoupper($_SESSION['username']); ?></strong> Anda telah login
      <button type="button" class="close" data-dismiss="alert" aria-label="Close">
        <span aria-hidden="true">&times;</span>
      </button>
    </div>
     <div class="card mt-4">
        <h4 class="container bg-danger text-white" > Soal Ujian</h4>
    <div class="scrool " style="overflow: scroll;  height: 33rem">


   
        <tbody>
            <?php
                include "koneksi.php";
                $sql = "SELECT * FROM soal ORDER BY RAND ()";
                $query = mysqli_query($koneksi,$sql) or die (mysqli_error($koneksi));
                $jumlah = mysqli_num_rows($query);
                $no = 0;
                while($data = mysqli_fetch_array($query)){?>
                     <table  >
                    <form action="kunci.php" method="post">
                        <input type="hidden" name="id[]" value="<?php echo $data['id']; ?>">
                        <input type="hidden" name="jumlah" value="<?php echo $jumlah; ?>">

<hr>
                        <tr>
                            <td width="50px"><?php echo $no = $no+1; ?></td>
                            <td><?php echo $data['soal'];?></td>
                        </tr>

                        <tr>
                            <td></td>
                            <td>A. <input name="pilihan[<?php echo $data['id']?>]" type="radio" value="A"><?php echo $data['a'];?></td>
                        </tr>
                        <tr>
                            <td></td>
                            <td>B. <input name="pilihan[<?php echo $data['id']?>]" type="radio" value="B"><?php echo $data['b'];?></td>
                        </tr>
                        <tr>
                            <td></td>
                            <td>C. <input name="pilihan[<?php echo $data['id']?>]" type="radio" value="C"><?php echo $data['c'];?></td>
                        </tr>
                        <tr>
                            <td></td>
                            <td>D. <input name="pilihan[<?php echo $data['id']?>]" type="radio" value="D"><?php echo $data['d'];?></td>
                        </tr>

                        

                <?php }
            ?>

                <tr>
                    <td></td>

                    <td ><hr>
                        <input class="btn btn-primary" type="submit" name="submit" value="Kirim" onclick="return confirm('Apakah Anda yakin dengan jawaban Anda?')">
                    </td>
                </tr>

            </form>

 </table>
        </tbody>
        </div>
        </div>
        </div>
   
    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="assets/jquery-3.4.1.slim.min.js" ></script>
    <script src="assets/popper.min.js" ></script>
    <script src="assets/js/bootstrap.min.js" ></script>

</body>
</html>