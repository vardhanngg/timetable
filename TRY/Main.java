import collections.*;
public class Main{
  public static void main(String... args){
    Sudoko s=new Sudoko();
    System.out.println("Question:");
    s.print();
    System.out.println(" ");
    boolean c;
    c=s.solve();
   if(c==true){
        System.out.println("solution:");
        s.print();}
    else 
        System.out.println("no solution");
}
}
